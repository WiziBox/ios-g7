#include "payload.h"
#define PAGE_16K 0x4000UL
static int overlaps(uint64_t a, uint64_t size, uint64_t b, uint64_t end)
{
    return a < end && size > (b > a ? b - a : 0);
}

static int magic_ok(const char *m)
{
    static const char want[] = "SWEETXNU";
    for (int i = 0; i < 8; i++)
        if (m[i] != want[i])
            return 0;
    return 1;
}

const char *g7_payload_check(const struct payload *p, uint64_t available,
    uint64_t rd_start, uint64_t rd_end, uint64_t shim_start,
    uint64_t shim_end, uint64_t dtb)
{
    if (available < sizeof(struct payload)) return "short payload header";
    if (!magic_ok(p->magic)) return "no SWEETXNU payload";
    if (p->version != 1 || (p->adt_off & 7) || (rd_start & 7))
        return "bad payload header";
    if (p->nsegs == 0 || p->nsegs > 32 ||
        sizeof(struct payload) + (uint64_t)p->nsegs * sizeof(struct payload_seg) > available)
        return "invalid segment table";
    if (p->phys_base != 0xb4000000ULL || p->mem_size != 0x49f00000ULL)
        return "payload is not configured for G7 safe RAM";
    if (p->virt_base > UINT64_MAX - p->mem_size ||
        p->kernel_end < p->virt_base || p->kernel_end - p->virt_base > p->mem_size ||
        p->entry_va < p->virt_base || p->entry_va - p->virt_base >= p->mem_size ||
        p->adt_size == 0 || p->adt_size > 0x100000 ||
        p->adt_off > available || p->adt_size > available - p->adt_off ||
        p->cmdline[BOOT_LINE_LENGTH - 1] != 0)
        return "invalid G7 payload layout";
    uint64_t adt_offset = p->kernel_end - p->virt_base;
    uint64_t args_offset = (adt_offset + p->adt_size + PAGE_16K - 1) & ~(PAGE_16K - 1);
    if (args_offset > p->mem_size - PAGE_16K)
        return "boot arguments exceed safe RAM";
    if (overlaps(p->phys_base, p->mem_size, rd_start, rd_end) ||
        overlaps(p->phys_base, p->mem_size, shim_start, shim_end) ||
        overlaps(p->phys_base, p->mem_size, dtb, dtb + 0x200000))
        return "safe RAM overlaps initrd/shim/FDT";
    int entry_found = 0;
    for (uint32_t i = 0; i < p->nsegs; ++i) {
        const struct payload_seg *seg = &p->segs[i];
        if (seg->vmaddr < p->virt_base || seg->vmaddr - p->virt_base > adt_offset ||
            seg->vmsize > adt_offset - (seg->vmaddr - p->virt_base) ||
            seg->file_size > seg->vmsize || seg->file_off > available ||
            seg->file_size > available - seg->file_off ||
            seg->file_off < sizeof(struct payload) + (uint64_t)p->nsegs * sizeof(struct payload_seg) ||
            seg->file_off > p->adt_off || seg->file_size > p->adt_off - seg->file_off ||
            (seg->vmaddr & 7) || (seg->file_off & 7))
            return "invalid segment range";
        if (seg->file_size && p->entry_va >= seg->vmaddr &&
            p->entry_va - seg->vmaddr < seg->file_size) entry_found = 1;
        for (uint32_t j = 0; j < i; ++j) {
            const struct payload_seg *prev = &p->segs[j];
            if (seg->vmsize && prev->vmsize && overlaps(seg->vmaddr, seg->vmsize,
                prev->vmaddr, prev->vmaddr + prev->vmsize))
                return "overlapping kernel segments";
        }
    }
    if (!entry_found) return "entry outside loaded segments";
    return 0;
}
