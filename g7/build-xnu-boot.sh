#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
STAGE_ONLY=0
if [ "${1:-}" = --stage-only ]; then STAGE_ONLY=1; shift; fi
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo 'usage: build-xnu-boot.sh [--stage-only] KERNEL [RAMDISK_ROOT_IMAGE]' >&2; exit 2
fi
KERNEL="$(realpath "$1")"
OUT="$ROOT/g7/shim/out/xnu-early"
NAME=g7-xnu-early-boot
EXTRA=()
if [ "$STAGE_ONLY" = 1 ]; then
    OUT="$ROOT/g7/shim/out/xnu-stage"
    NAME=g7-xnu-stage-boot
    EXTRA+=(-DG7_LOADER_STAGE_ONLY)
else
    python3 "$ROOT/g7/verify-kernel.py" "$KERNEL"
fi
mkdir -p "$OUT"
python3 "$ROOT/g7/mkadt-g7.py" "$OUT/g7.adt"
CMDLINE='debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=md0 sweetkeys=0 sweettouch=0 sweetusb=0 sweetfb_native=1 ufsrw=0 wdt=-1'
RAMDISK=()
if [ "$#" = 2 ]; then RAMDISK+=(--ramdisk "$(realpath "$2")"); fi
python3 "$ROOT/tools/mkpayload.py" "$KERNEL" "$OUT/g7.adt" "$OUT/payload.bin" \
    --cmdline "$CMDLINE" "${RAMDISK[@]}"
cd "$ROOT/g7/shim"
CC=aarch64-linux-gnu-gcc
CFLAGS=(-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only
        -mstrict-align -fno-stack-protector -Wall -Wextra -Werror)
SOURCES=(start.S g7_xnu.c console.c splash.c fdt.c loader.c payload.c)
OBJECTS=()
for source in "${SOURCES[@]}"; do
    object="$OUT/${source%.*}.o"
    "$CC" "${CFLAGS[@]}" "${EXTRA[@]}" -c "$source" -o "$object"
    OBJECTS+=("$object")
    if [ "$source" != start.S ] && aarch64-linux-gnu-readelf -r "$object" | grep -q ABS64; then
        echo "non-relocatable object: $source" >&2; exit 1
    fi
done
"$CC" "${CFLAGS[@]}" -static -T shim.ld -Wl,--build-id=none \
    -Wl,--no-warn-rwx-segments -Wl,-N "${OBJECTS[@]}" -o "$OUT/g7-xnu-shim.elf"
aarch64-linux-gnu-objcopy -O binary "$OUT/g7-xnu-shim.elf" "$OUT/Image"
size_hex=$(aarch64-linux-gnu-nm "$OUT/g7-xnu-shim.elf" | awk '$3=="_end"{print $1}')
test -n "$size_hex"
truncate -s "$((16#$size_hex))" "$OUT/Image"
python3 "$ROOT/g7/pack-diag.py" "$OUT" --name "$NAME" \
    --kind 'G7 XNU bootstrap; no persistent storage' --ramdisk "$OUT/payload.bin"
