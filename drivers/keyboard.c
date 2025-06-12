#include "keyboard.h"
#include "cpu/isr.h"
#include "cpu/memlayout.h"
#include "console.h"
#include "port.h"
#include "kernel/mem.h"

/*
 * Mapping of keyboard scancodes to ASCII symbols for an ordinary US keyboard
 * without any modifiers pressed.
 */
static const char sc_ascii[] = {
    '?', '?', '1', '2', '3', '4', '5', '6',
    '7', '8', '9', '0', '-', '=', '?', '?', 'q', 'w', 'e', 'r', 't', 'y',
    'u', 'i', 'o', 'p', '[', ']', '\n', '?', 'a', 's', 'd', 'f', 'g',
    'h', 'j', 'k', 'l', ';', '\'', '`', '?', '\\', 'z', 'x', 'c', 'v',
    'b', 'n', 'm', ',', '.', '/', '?', '?', '?', ' ',
};

/* Same mapping but for when Shift is held down. */
static const char sc_ascii_shift[] = {
    '?', '?', '!', '@', '#', '$', '%', '^',
    '&', '*', '(', ')', '_', '+', '?', '?', 'Q', 'W', 'E', 'R', 'T', 'Y',
    'U', 'I', 'O', 'P', '{', '}', '\n', '?', 'A', 'S', 'D', 'F', 'G',
    'H', 'J', 'K', 'L', ':', '"', '~', '?', '|', 'Z', 'X', 'C', 'V',
    'B', 'N', 'M', '<', '>', '?', '?', '?', '?', ' ',
};

static int lshift;
static int rshift;

enum { kbd_buf_capacity = PGSIZE };

static void interrupt_handler(registers_t *r) {
    uint8_t scancode = port_byte_in(0x60);

    /*
     * Scancodes for shift keys. When one of them is pressed or released we
     * simply update our state and do not output anything.
     */
    enum {
        LSHIFT_PRESS  = 0x2a,
        LSHIFT_RELEASE = 0xaa,
        RSHIFT_PRESS  = 0x36,
        RSHIFT_RELEASE = 0xb6,
    };

    if (scancode == LSHIFT_PRESS) {
        lshift = 1;
        return;
    } else if (scancode == RSHIFT_PRESS) {
        rshift = 1;
        return;
    } else if (scancode == LSHIFT_RELEASE) {
        lshift = 0;
        return;
    } else if (scancode == RSHIFT_RELEASE) {
        rshift = 0;
        return;
    }

    if (scancode < sizeof(sc_ascii)) {
        const char *table = (lshift || rshift) ? sc_ascii_shift : sc_ascii;
        char c = table[scancode];
        if (kbd_buf_size < kbd_buf_capacity) {
            kbd_buf[kbd_buf_size++] = c;
        }
        char string[] = {c, '\0'};
        printk(string);
    }
}

char* kbd_buf;
unsigned kbd_buf_size;

void init_keyboard() {
    kbd_buf = kalloc();

    register_interrupt_handler(IRQ1, interrupt_handler);
}
