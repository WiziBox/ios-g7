#pragma once
#include <stddef.h>
#include <stdint.h>
/* No fallback address: require the bootloader's actual FDT to agree. */
int g7_splash_region(const unsigned char *dtb, size_t available,
                     uint64_t *base, uint64_t *size);
