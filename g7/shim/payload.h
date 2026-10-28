#pragma once
#include <stdint.h>
#define BOOT_LINE_LENGTH 608
struct payload_seg {
    uint64_t vmaddr, vmsize, file_off, file_size;
};

struct payload {
    char magic[8];
    uint32_t version, nsegs;
    uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
    uint64_t phys_base, mem_size;
    char cmdline[BOOT_LINE_LENGTH];
    struct payload_seg segs[];
};

const char *g7_payload_check(const struct payload *p, uint64_t available,
    uint64_t rd_start, uint64_t rd_end, uint64_t shim_start,
    uint64_t shim_end, uint64_t dtb);
