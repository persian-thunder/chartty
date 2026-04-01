CC     = cc
CFLAGS = -O2 -Wall -Wextra -Wno-unused-parameter

UNAME := $(shell uname)
ifeq ($(UNAME), Darwin)
    LDFLAGS = -lm
else
    LDFLAGS = -ldl -lm
endif

.PHONY: all clean shader

all: renderer shader

renderer: renderer.c
	$(CC) $(CFLAGS) -o renderer renderer.c $(LDFLAGS)

shader:
	bash compile_shader.sh

clean:
	rm -f renderer shader.so shader.so.tmp shader_full.c shader_error.txt
