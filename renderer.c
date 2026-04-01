/* renderer.c — Chartty ASCII live-code renderer (C port of renderer.py)
 *
 * Architecture:
 *   - Shader loaded as a shared library (shader.so) via dlopen/dlsym
 *   - On shader.so mtime change → dlclose old, dlopen new (zero-copy hot-swap)
 *   - Full frame built into a static buffer, single write() per frame
 *   - LUT: 256 pre-built ANSI colour escape strings (rebuilt on palette change)
 *   - Charset: UTF-8 codepoints parsed into per-entry arrays (no strlen in loop)
 */

#ifdef __APPLE__
#  define _DARWIN_C_SOURCE 1
#else
#  define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <errno.h>

/* ── tunables ────────────────────────────────────────────────────────────── */
#define MAX_CHARS     128
#define MAX_CHAR_LEN  8
#define LUT_SIZE      256
#define LUT_ESC_LEN   24   /* "\033[38;2;255;255;255m\0" fits in 24 bytes */
#define OUTBUF_SIZE   (4 * 1024 * 1024)
#define PATH_BUF      512

/* ── shader function signature ───────────────────────────────────────────── */
typedef void (*shader_fn_t)(double x, double y, double t,
                             int cols, int rows,
                             double *v_out, double *c_out);

/* ── globals ─────────────────────────────────────────────────────────────── */
static char         g_outbuf[OUTBUF_SIZE];

static char         g_lut[LUT_SIZE][LUT_ESC_LEN];
static int          g_lut_len[LUT_SIZE];

static char         g_chars[MAX_CHARS][MAX_CHAR_LEN];
static int          g_char_len[MAX_CHARS];
static int          g_n_chars = 0;

static volatile int g_running      = 1;
static void        *g_shader_hdl   = NULL;
static shader_fn_t  g_shader_fn    = NULL;
static char         g_pal_name[64] = "rainbow";
static char         g_err_msg[512] = "";
static int          g_has_err      = 0;

/* paths (filled in main from argv[0]) */
static char g_shader_so [PATH_BUF];
static char g_chars_file[PATH_BUF];
static char g_pal_file  [PATH_BUF];
static char g_err_file  [PATH_BUF];

/* ── signal handler ──────────────────────────────────────────────────────── */
static void on_signal(int sig) { (void)sig; g_running = 0; }

/* ── monotonic clock ─────────────────────────────────────────────────────── */
static double mono_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* ── file mtime ──────────────────────────────────────────────────────────── */
static double file_mtime(const char *path) {
    struct stat st;
    if (stat(path, &st) != 0) return -1.0;
#ifdef __APPLE__
    return (double)st.st_mtimespec.tv_sec
         + (double)st.st_mtimespec.tv_nsec * 1e-9;
#else
    return (double)st.st_mtim.tv_sec
         + (double)st.st_mtim.tv_nsec * 1e-9;
#endif
}

/* ── HSV → RGB helper ────────────────────────────────────────────────────── */
static void hsv2rgb(double h, double s, double v,
                    int *r, int *g, int *b)
{
    h = fmod(h, 1.0); if (h < 0.0) h += 1.0;
    int    i  = (int)(h * 6.0);
    double f  = h * 6.0 - i;
    double p  = v * (1.0 - s);
    double q  = v * (1.0 - f * s);
    double t2 = v * (1.0 - (1.0 - f) * s);
    double rv, gv, bv;
    switch (i % 6) {
        case 0: rv=v;  gv=t2; bv=p;  break;
        case 1: rv=q;  gv=v;  bv=p;  break;
        case 2: rv=p;  gv=v;  bv=t2; break;
        case 3: rv=p;  gv=q;  bv=v;  break;
        case 4: rv=t2; gv=p;  bv=v;  break;
        default:rv=v;  gv=p;  bv=q;  break;
    }
    *r = (int)(rv * 255.0);
    *g = (int)(gv * 255.0);
    *b = (int)(bv * 255.0);
}

/* ── build 256-entry colour LUT ──────────────────────────────────────────── */
#define CLAMP255(x) ((x) < 0 ? 0 : ((x) > 255 ? 255 : (x)))

static void make_lut(const char *name) {
    for (int i = 0; i < 256; i++) {
        double n = i / 255.0;
        int r, g, b;
        if (!strcmp(name, "green")) {
            r = 0;
            g = (int)(30.0 + n * 225.0);
            b = (int)(n * 40.0);
        } else if (!strcmp(name, "fire")) {
            r = (int)(n * 3.0 * 255.0);
            g = (int)((n - 0.33) * 3.0 * 255.0);
            b = (int)((n - 0.66) * 3.0 * 255.0);
        } else if (!strcmp(name, "ice")) {
            r = (int)(n * 80.0);
            g = (int)(180.0 + n * 75.0);
            b = 255;
        } else if (!strcmp(name, "plasma")) {
            r = (int)(128.0 + 127.0 * sin(n * M_PI * 2.0));
            g = (int)(128.0 + 127.0 * sin(n * M_PI * 2.0 + 2.094));
            b = (int)(128.0 + 127.0 * sin(n * M_PI * 2.0 + 4.189));
        } else if (!strcmp(name, "gold")) {
            r = (int)(n * 2.0 * 255.0);
            g = (int)(n * 180.0);
            b = (int)(n * 20.0);
        } else if (!strcmp(name, "rose")) {
            hsv2rgb(0.9 + n * 0.15, 0.8, n, &r, &g, &b);
        } else if (!strcmp(name, "neon")) {
            hsv2rgb(0.55 + n * 0.1, 1.0, n, &r, &g, &b);
        } else if (!strcmp(name, "mono")) {
            r = g = b = (int)(n * 255.0);
        } else { /* rainbow (default) */
            hsv2rgb(n * 0.85, 1.0, 1.0, &r, &g, &b);
        }
        r = CLAMP255(r); g = CLAMP255(g); b = CLAMP255(b);
        g_lut_len[i] = snprintf(g_lut[i], LUT_ESC_LEN,
                                "\033[38;2;%d;%d;%dm", r, g, b);
    }
}

/* ── parse UTF-8 string into per-codepoint table ─────────────────────────── */
static void parse_chars(const char *s) {
    g_n_chars = 0;
    const unsigned char *p = (const unsigned char *)s;
    while (*p && g_n_chars < MAX_CHARS) {
        int len;
        if      ((*p & 0x80) == 0x00) len = 1;
        else if ((*p & 0xE0) == 0xC0) len = 2;
        else if ((*p & 0xF0) == 0xE0) len = 3;
        else if ((*p & 0xF8) == 0xF0) len = 4;
        else                           len = 1;
        if (len > MAX_CHAR_LEN - 1) len = MAX_CHAR_LEN - 1;
        memcpy(g_chars[g_n_chars], p, (size_t)len);
        g_chars[g_n_chars][len] = '\0';
        g_char_len[g_n_chars]   = len;
        g_n_chars++;
        p += len;
    }
    if (g_n_chars < 1) {   /* fallback: space */
        g_chars[0][0] = ' '; g_chars[0][1] = '\0';
        g_char_len[0] = 1;   g_n_chars = 1;
    }
}

/* ── null shader (used while shader.so is absent or invalid) ─────────────── */
static void null_shader(double x, double y, double t,
                         int cols, int rows,
                         double *v_out, double *c_out)
{
    (void)x; (void)y; (void)t; (void)cols; (void)rows;
    *v_out = 0.0; *c_out = 0.0;
}

/* ── load / hot-swap shader.so ───────────────────────────────────────────── */
/*
 * macOS dyld caches shared libraries by path — dlopen()-ing the same path
 * after a recompile returns the OLD in-memory image.  Fix: copy shader.so to
 * a unique temp file each time so dyld sees a genuinely new path.
 */
static char g_shader_tmp[PATH_BUF] = "";  /* path of currently-loaded tmp .so */
static int  g_shader_gen = 0;             /* generation counter for unique names */

static void load_shader(void) {
    /* Build a unique temp path: /tmp/chartty_<pid>_<gen>.so */
    char tmp_path[PATH_BUF];
    snprintf(tmp_path, sizeof(tmp_path), "/tmp/chartty_%d_%d.so",
             (int)getpid(), ++g_shader_gen);

    /* Copy shader.so → tmp_path */
    {
        int src = open(g_shader_so, O_RDONLY);
        if (src < 0) {
            snprintf(g_err_msg, sizeof(g_err_msg),
                     "open shader.so: %s", strerror(errno));
            g_has_err = 1;
            return;
        }
        int dst = open(tmp_path, O_WRONLY | O_CREAT | O_TRUNC, 0755);
        if (dst < 0) {
            close(src);
            snprintf(g_err_msg, sizeof(g_err_msg),
                     "open tmp: %s", strerror(errno));
            g_has_err = 1;
            return;
        }
        char cpbuf[65536];
        ssize_t n;
        while ((n = read(src, cpbuf, sizeof(cpbuf))) > 0)
            write(dst, cpbuf, (size_t)n);
        close(src);
        close(dst);
    }

    void *h = dlopen(tmp_path, RTLD_NOW | RTLD_LOCAL);
    if (!h) {
        unlink(tmp_path);
        snprintf(g_err_msg, sizeof(g_err_msg), "dlopen: %s", dlerror());
        g_has_err = 1;
        return;
    }

    /* cast through uintptr_t to silence -Wpedantic pointer-to-object warning */
    shader_fn_t fn = (shader_fn_t)(uintptr_t)dlsym(h, "shader");
    if (!fn) {
        unlink(tmp_path);
        dlclose(h);
        snprintf(g_err_msg, sizeof(g_err_msg), "dlsym: %s", dlerror());
        g_has_err = 1;
        return;
    }

    /* swap: briefly null so the render loop falls back to null_shader */
    g_shader_fn = NULL;
    if (g_shader_hdl) {
        dlclose(g_shader_hdl);
        if (g_shader_tmp[0]) unlink(g_shader_tmp);  /* remove old temp */
    }
    g_shader_hdl = h;
    g_shader_fn  = fn;
    strncpy(g_shader_tmp, tmp_path, sizeof(g_shader_tmp) - 1);
    g_has_err    = 0;
    g_err_msg[0] = '\0';
}

/* ── render one frame into g_outbuf, returns byte count ─────────────────── */
static size_t render_frame(int cols, int rows, double t) {
    char       *p   = g_outbuf;
    const char *end = g_outbuf + OUTBUF_SIZE - 2048; /* safety margin */

    /* cursor to top-left */
    memcpy(p, "\033[H", 3); p += 3;

    int        nc = (g_n_chars > 0) ? g_n_chars : 1;
    shader_fn_t fn = g_shader_fn ? g_shader_fn : null_shader;

    for (int y = 0; y < rows; y++) {
        int prev_ci = -1;
        for (int x = 0; x < cols; x++) {
            if (p >= end) goto done;

            double vv = 0.0, cc = 0.0;
            fn((double)x, (double)y, t, cols, rows, &vv, &cc);

            /* map value → char index */
            int vi = (int)(vv * (double)(nc - 1) + 0.5);
            if (vi <  0 ) vi = 0;
            if (vi >= nc) vi = nc - 1;

            /* map colour → LUT index */
            int ci = (int)(cc * 255.0 + 0.5);
            if (ci <   0) ci = 0;
            if (ci > 255) ci = 255;

            /* only emit escape when colour changes (skip redundant sequences) */
            if (ci != prev_ci) {
                memcpy(p, g_lut[ci], (size_t)g_lut_len[ci]);
                p += g_lut_len[ci];
                prev_ci = ci;
            }

            memcpy(p, g_chars[vi], (size_t)g_char_len[vi]);
            p += g_char_len[vi];
        }
        /* reset colour + newline at end of each row */
        memcpy(p, "\033[0m\n", 5); p += 5;
    }

done:
    /* status line */
    if (g_has_err) {
        int n = snprintf(p, (size_t)(end - p),
                         "\033[31m X  %.110s\033[0m", g_err_msg);
        if (n > 0) p += n;
    } else {
        int n = snprintf(p, (size_t)(end - p),
                         "\033[2m *  %s  %dx%d  t=%.1f\033[0m",
                         g_pal_name, cols, rows, t);
        if (n > 0) p += n;
    }

    return (size_t)(p - g_outbuf);
}

/* ── read a small text file into buf, strip trailing newline ─────────────── */
static int read_file(const char *path, char *buf, size_t bufsz) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    size_t n = fread(buf, 1, bufsz - 1, f);
    fclose(f);
    buf[n] = '\0';
    while (n > 0 && (buf[n-1] == '\n' || buf[n-1] == '\r')) buf[--n] = '\0';
    return (int)n;
}

/* ── main ────────────────────────────────────────────────────────────────── */
int main(int argc, char *argv[]) {
    (void)argc;

    /* derive project directory from argv[0] */
    char dir[PATH_BUF];
    {
        char tmp[PATH_BUF];
        strncpy(tmp, argv[0], PATH_BUF - 1); tmp[PATH_BUF - 1] = '\0';
        char *slash = strrchr(tmp, '/');
        if (slash) { *slash = '\0'; strncpy(dir, tmp, PATH_BUF - 1); }
        else        { getcwd(dir, PATH_BUF); }
    }
    snprintf(g_shader_so,  PATH_BUF, "%s/shader.so",        dir);
    snprintf(g_chars_file, PATH_BUF, "%s/chars.txt",        dir);
    snprintf(g_pal_file,   PATH_BUF, "%s/palette.txt",      dir);
    snprintf(g_err_file,   PATH_BUF, "%s/shader_error.txt", dir);

    signal(SIGINT,  on_signal);
    signal(SIGTERM, on_signal);

    /* defaults */
    parse_chars(" \xc2\xb7:\xe2\x94\x82\xe2\x96\x92\xe2\x96\x88"); /* " ·:│▒█" */
    make_lut("rainbow");

    /* hide cursor + clear screen */
    const char *init = "\033[?25l\033[2J";
    write(STDOUT_FILENO, init, strlen(init));

    double so_mtime    = -2.0;
    double chars_mtime = -2.0;
    double pal_mtime   = -2.0;
    double err_mtime   = -2.0;

    double t = 0.0;

    while (g_running) {
        double frame_start = mono_sec();

        /* ── hot-reload shader.so ─────────────────────────────────────── */
        {
            double mt = file_mtime(g_shader_so);
            if (mt > 0.0 && mt != so_mtime) {
                so_mtime = mt;
                load_shader();
            }
        }

        /* ── read shader_error.txt if updated ───────────────────────────── */
        {
            double et = file_mtime(g_err_file);
            if (et > 0.0 && et != err_mtime) {
                err_mtime = et;
                char buf[512];
                if (read_file(g_err_file, buf, sizeof(buf)) > 0) {
                    /* keep only the first meaningful line */
                    char *nl = strchr(buf, '\n');
                    if (nl) *nl = '\0';
                    strncpy(g_err_msg, buf, sizeof(g_err_msg) - 1);
                    g_has_err = 1;
                }
            }
        }

        /* ── hot-reload chars.txt ─────────────────────────────────────── */
        {
            double mt = file_mtime(g_chars_file);
            if (mt > 0.0 && mt != chars_mtime) {
                chars_mtime = mt;
                char buf[512];
                int  n = read_file(g_chars_file, buf, sizeof(buf));
                if (n >= 2) parse_chars(buf);
            }
        }

        /* ── hot-reload palette.txt ───────────────────────────────────── */
        {
            double mt = file_mtime(g_pal_file);
            if (mt > 0.0 && mt != pal_mtime) {
                pal_mtime = mt;
                char buf[64];
                if (read_file(g_pal_file, buf, sizeof(buf)) > 0) {
                    strncpy(g_pal_name, buf, sizeof(g_pal_name) - 1);
                    make_lut(g_pal_name);
                }
            }
        }

        /* ── terminal size ────────────────────────────────────────────── */
        int cols, rows;
        {
            struct winsize ws;
            if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0
                && ws.ws_col > 0 && ws.ws_row > 0) {
                cols = (int)ws.ws_col;
                rows = (int)ws.ws_row - 1; /* reserve one row for status */
            } else {
                cols = 80; rows = 23;
            }
        }

        /* ── render + flush ───────────────────────────────────────────── */
        size_t len = render_frame(cols, rows, t);
        write(STDOUT_FILENO, g_outbuf, len);

        t += 0.06;

        /* ── pace to ~20 fps (50 ms target) ──────────────────────────── */
        double elapsed = mono_sec() - frame_start;
        double rem     = 0.05 - elapsed;
        if (rem > 0.0) {
            struct timespec ts = { 0, (long)(rem * 1e9) };
            nanosleep(&ts, NULL);
        }
    }

    /* restore terminal */
    const char *restore = "\033[?25h\033[0m\n";
    write(STDOUT_FILENO, restore, strlen(restore));
    if (g_shader_hdl) {
        dlclose(g_shader_hdl);
        if (g_shader_tmp[0]) unlink(g_shader_tmp);
    }
    return 0;
}
