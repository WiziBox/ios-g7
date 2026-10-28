#include "splash.h"

static uint32_t be32(const unsigned char *p)
{
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 |
           (uint32_t)p[2] << 8 | p[3];
}

static int eq(const unsigned char *p, size_t n, const char *s)
{
    size_t i = 0;
    while (i < n && s[i] && p[i] == (unsigned char)s[i]) ++i;
    return i == n && !s[i];
}

/* Bounded FDT walker. Only accept the exact G7 fixed reserved-memory node,
 * 64-bit address/size cells, and known dump address/length. No MMIO here. */
int g7_splash_region(const unsigned char *b, size_t available,
                     uint64_t *base, uint64_t *size)
{
    if (available < 40 || be32(b) != 0xd00dfeed) return 0;
    uint32_t total = be32(b + 4), off = be32(b + 8);
    uint32_t strings = be32(b + 12), slen = be32(b + 32);
    uint32_t len = be32(b + 36);
    if (total > available || total < 40 || off < 40 || strings < 40 ||
        off > total || len > total - off || (off & 3) ||
        strings > total || slen > total - strings) return 0;
    size_t end = (size_t)off + len;
    int depth = 0, reserved = 0, target = 0, ac = 0, sc = 0, found = 0;
    while (off <= end && end - off >= 4) {
        uint32_t token = be32(b + off); off += 4;
        if (token == 1) {
            size_t start = off;
            while (off < end && b[off]) ++off;
            if (off == end) return 0;
            ++depth;
            if (depth == 2 && eq(b + start, off - start, "reserved-memory")) {
                reserved = depth; ac = sc = 0;
            }
            if (reserved && depth == reserved + 1 &&
                eq(b + start, off - start, "cont_splash_region@9d400000"))
                target = depth;
            off = (off + 4) & ~3U;
        } else if (token == 2) {
            if (!depth) return 0;
            if (target == depth) target = 0;
            if (reserved == depth) reserved = 0;
            --depth;
        } else if (token == 3) {
            if (!depth || end - off < 8) return 0;
            uint32_t n = be32(b + off), name = be32(b + off + 4); off += 8;
            if (n > end - off || name >= slen) return 0;
            size_t ni = name;
            while (ni < slen && b[strings + ni]) ++ni;
            if (ni == slen) return 0;
            const unsigned char *key = b + strings + name;
            if (reserved == depth && n == 4) {
                if (eq(key, ni - name, "#address-cells")) ac = be32(b + off);
                if (eq(key, ni - name, "#size-cells")) sc = be32(b + off);
            }
            if (target == depth && eq(key, ni - name, "reg")) {
                if (ac != 2 || sc != 2 || n != 16 || found) return 0;
                uint64_t a = (uint64_t)be32(b + off) << 32 | be32(b + off + 4);
                uint64_t s = (uint64_t)be32(b + off + 8) << 32 | be32(b + off + 12);
                if (a != 0x9d400000ULL || s != 0x2400000ULL) return 0;
                *base = a; *size = s; found = 1;
            }
            off = (off + n + 3) & ~3U;
        } else if (token == 4) {
            continue;
        } else if (token == 9) {
            return depth == 0 && found;
        } else return 0;
    }
    return 0;
}
