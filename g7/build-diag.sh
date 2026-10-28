#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
DIR="$ROOT/g7/shim"
OUT="$DIR/out/diag-v2"
mkdir -p "$OUT"
cd "$DIR"
CC="${CROSS_COMPILE:-aarch64-linux-gnu-}gcc"
CFLAGS=(-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only
        -mstrict-align -fno-stack-protector -Wall -Wextra -Werror)
for source in start.S g7_diag.c splash.c; do
    "$CC" "${CFLAGS[@]}" -c "$source" -o "$OUT/${source%.*}.o"
done
if aarch64-linux-gnu-readelf -r "$OUT/g7_diag.o" "$OUT/splash.o" | grep -q ABS64; then
    echo 'ERROR: non-relocatable C object' >&2; exit 1
fi
"$CC" "${CFLAGS[@]}" -static -T shim.ld -Wl,--build-id=none \
    -Wl,--no-warn-rwx-segments -Wl,-N \
    "$OUT/start.o" "$OUT/g7_diag.o" "$OUT/splash.o" -o "$OUT/g7-diag.elf"
aarch64-linux-gnu-objcopy -O binary "$OUT/g7-diag.elf" "$OUT/Image"
size_hex=$(aarch64-linux-gnu-nm "$OUT/g7-diag.elf" | awk '$3=="_end"{print $1}')
test -n "$size_hex"
truncate -s "$((16#$size_hex))" "$OUT/Image"
python3 "$ROOT/g7/pack-diag.py" "$OUT"
