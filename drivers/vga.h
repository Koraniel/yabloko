#pragma once

enum vga_color {
    VGA_BLACK = 0,
    VGA_BLUE,
    VGA_GREEN,
    VGA_CYAN,
    VGA_RED,
    VGA_MAGENTA,
    VGA_BROWN,
    VGA_LIGHT_GRAY,
    VGA_DARK_GRAY,
    VGA_LIGHT_BLUE,
    VGA_LIGHT_GREEN,
    VGA_LIGHT_CYAN,
    VGA_LIGHT_RED,
    VGA_LIGHT_MAGENTA,
    VGA_YELLOW,
    VGA_WHITE,
};

static inline unsigned char vga_entry_color(enum vga_color fg, enum vga_color bg) {
    return (bg << 4) | fg;
}

void vga_set_char(unsigned offset, char c, unsigned char color);
void vga_clear_screen();

void vga_print_string(const char* s);

void vga_backspace();

void vgaMode13();
void vgaMode3();
