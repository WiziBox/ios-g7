#include <stdint.h>
#include "splash.h"

/* A display-only entry diagnostic: no UFS/GIC/PSCI/partition operations.
 * Whole-region monochrome needs no unverified pixel format or scanout stride.
 * This is not an XNU/iOS boot image. */
volatile struct {
    uint64_t magic, dtb, mpidr, current_el, cntfrq, mmfr0, midr;
    uint64_t stage, exception_slot, esr, elr, far;
} g7_diag;

#define READ(r) ({ uint64_t v; __asm__ volatile("mrs %0, " r : "=r"(v)); v; })
extern char _head[], _end[];

static void wait_second(void)
{
    uint64_t start = READ("cntpct_el0"), freq = READ("cntfrq_el0");
    if (freq < 1000000 || freq > 1000000000) {
        for (volatile unsigned i = 0; i < 20000000; ++i) {}
        return;
    }
    while (READ("cntpct_el0") - start < freq) {}
}

void shim_main(uint64_t dtb)
{
    g7_diag.magic = 0x4737444941473032ULL;
    g7_diag.dtb = dtb;
    g7_diag.current_el = READ("CurrentEL");
    g7_diag.mpidr = READ("mpidr_el1");
    g7_diag.cntfrq = READ("cntfrq_el0");
    g7_diag.mmfr0 = READ("id_aa64mmfr0_el1");
    g7_diag.midr = READ("midr_el1");
    g7_diag.stage = 1;
    uint64_t base = 0, size = 0;
    /* Qualcomm RAM window from the local G7 dump; cap FDT reads at 2 MiB. */
    if ((dtb & 7) || dtb < 0x80000000ULL || dtb > 0x17dda0000ULL ||
        !g7_splash_region((const unsigned char *)dtb, 0x200000, &base, &size))
        goto halt;
    /* Never overwrite our own code or the passed FDT even on a bad layout. */
    if (((uintptr_t)_head < base + size && (uintptr_t)_end > base) ||
        (dtb < base + size && dtb + 0x200000 > base)) goto halt;
    g7_diag.stage = 2;
    for (unsigned frame = 0; ; ++frame) {
        volatile uint32_t *pixels = (volatile uint32_t *)(uintptr_t)base;
        uint32_t color = frame & 1 ? 0xff000000U : 0xffffffffU;
        for (uint64_t i = 0; i < size / 4; ++i) pixels[i] = color;
        __asm__ volatile("dsb sy" ::: "memory");
        g7_diag.stage = 3 + frame;
        wait_second();
    }
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
    g7_diag.exception_slot = slot + 1;
    g7_diag.esr = READ("esr_el1");
    g7_diag.elr = READ("elr_el1");
    g7_diag.far = READ("far_el1");
    __asm__ volatile("dsb sy" ::: "memory");
    for (;;) __asm__ volatile("wfe");
}
