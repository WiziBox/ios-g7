#include <stdint.h>
#include "console.h"
#include "splash.h"
#include "loader.h"

#define READ(r) ({ uint64_t v; __asm__ volatile("mrs %0, " r : "=r"(v)); v; })
static int display_ready;
extern char _head[], _end[];

void shim_main(uint64_t dtb)
{
    uint64_t base = 0, size = 0;
    if ((dtb & 7) || dtb < 0x80000000ULL || dtb > 0x17dda0000ULL ||
        !g7_splash_region((const unsigned char *)dtb, 0x200000, &base, &size))
        goto halt;
    if (((uintptr_t)_head < base + size && (uintptr_t)_end > base) ||
        (dtb < base + size && dtb + 0x200000 > base)) goto halt;
    con_fb = (volatile uint32_t *)(uintptr_t)base;
    con_stride = 5760;
    display_ready = 1;
    con_clear(0xff000000U);
    con_str("G7", "XNU EARLY BOOT LOADER");
    con_hex("EL", READ("CurrentEL"));
    con_hex("DTB", dtb);
    con_hex("MMFR0", READ("id_aa64mmfr0_el1"));
    con_str("RAM", "B4000000..FDF00000; NO UFS");
    const char *error = loader_boot(dtb);
    con_str("STOP", error);
    __asm__ volatile("dsb sy" ::: "memory");
halt:
    for (;;) __asm__ volatile("wfe");
}

void secondary_main(uint64_t idx)
{
    (void)idx;
    for (;;) __asm__ volatile("wfe");
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
    (void)regs;
    if (display_ready) {
        con_clear(BLUE);
        con_str("PANIC", "G7 SHIM EXCEPTION");
        con_hex("SLOT", slot);
        con_hex("ESR", READ("esr_el1"));
        con_hex("ELR", READ("elr_el1"));
        con_hex("FAR", READ("far_el1"));
        __asm__ volatile("dsb sy" ::: "memory");
    }
    for (;;) __asm__ volatile("wfe");
}
