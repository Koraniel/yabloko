#pragma once

#include <stdint.h>

void run_elf(const char* name);
_Noreturn void killproc();
uintptr_t user_readable_after(uintptr_t ptr);
