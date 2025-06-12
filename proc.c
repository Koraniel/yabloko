#include "elf.h"
#include "proc.h"
#include "fs/fs.h"
#include "cpu/gdt.h"
#include "cpu/isr.h"
#include "cpu/memlayout.h"
#include "kernel/mem.h"
#include "lib/string.h"
#include "console.h"

struct context {
    // matches the behavior of swtch()
    uint32_t edi, esi, ebp, ebx;
    uint32_t eip; // return address for swtch()
};

struct kstack {
    uint32_t space[400];
    struct context context;
    registers_t trapframe;
    char bottom[];
};

struct task {
    struct taskstate tss;
    pde_t *pgdir;
    struct kstack stack;
};

struct vm {
    void *kernel_thread;
    struct task *user_task;
} vm;

void trapret();
void swtch(void** oldstack, void* newstack);

void run_elf(const char* name) {
    struct stat statbuf;
    if (stat(name, &statbuf) != 0) {
        printk(name);
        printk(": file not found\n");
        return;
    }
    if (!vm.user_task) {
        vm.user_task = kalloc();
    }
    vm.user_task->pgdir = setupkvm();
    uintptr_t file_top = USER_BASE + statbuf.size;
    allocuvm(vm.user_task->pgdir, USER_BASE, file_top);
    allocuvm(vm.user_task->pgdir, USER_STACK_BASE - 2 * PGSIZE, USER_STACK_BASE);
    switchuvm(&vm.user_task->tss, vm.user_task->stack.bottom, vm.user_task->pgdir);

    if (read_file(&statbuf, (void*)USER_BASE, 100 << 20) <= 0) {
        printk(name);
        printk(": file not found\n");
        return;
    }
    Elf32_Ehdr *hdr = (void*)USER_BASE;

    uintptr_t prog_top = file_top;
    for (int i = 0; i < hdr->e_phnum; i++) {
        Elf32_Phdr *phdr = (void*)((char*)hdr + hdr->e_phoff + i * hdr->e_phentsize);
        uintptr_t end = phdr->p_vaddr + phdr->p_memsz;
        if (end > prog_top)
            prog_top = end;
    }
    if (prog_top > file_top)
        allocuvm(vm.user_task->pgdir, file_top, prog_top);

    struct kstack *u = &vm.user_task->stack;
    memset(u, 0, sizeof(*u));
    u->context.eip = (uint32_t)trapret;

    registers_t *tf = &u->trapframe;
    tf->eip = hdr->e_entry;
    tf->cs = (SEG_UCODE << 3) | DPL_USER;
    tf->ds = (SEG_UDATA << 3) | DPL_USER;
    tf->es = tf->ds;
    tf->fs = tf->ds;
    tf->gs = tf->ds;
    tf->ss = tf->ds;
    tf->eflags = FL_IF;
    tf->useresp = USER_STACK_BASE;

    // initialization done, now switch to the process
    swtch(&vm.kernel_thread, &u->context);

    // process has finished
}

_Noreturn void killproc() {
    void* task_stack;
    switchkvm();
    freevm(vm.user_task->pgdir);
    sti();
    swtch(&task_stack, vm.kernel_thread);
    __builtin_unreachable();
}

// Return how many bytes starting from ptr are mapped as user readable.
// Returns 0 if ptr is outside of user space or unmapped.
uintptr_t user_readable_after(uintptr_t ptr) {
    if (ptr >= KERNBASE || !vm.user_task)
        return 0;

    pde_t *pgdir = vm.user_task->pgdir;
    uintptr_t va = ptr;
    uintptr_t end = ptr;

    while (va < KERNBASE) {
        pde_t pde = pgdir[PDX(va)];
        if (!(pde & PTE_P))
            break;

        pte_t *pt = (pte_t*)P2V(PTE_ADDR(pde));
        pte_t pte = pt[PTX(va)];
        if (!(pte & PTE_P) || !(pte & PTE_U))
            break;

        uintptr_t page_end = PGROUNDDOWN(va) + PGSIZE;
        end = page_end;
        va = page_end;
    }

    return end > ptr ? end - ptr : 0;
}
