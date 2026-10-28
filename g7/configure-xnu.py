#!/usr/bin/env python3
"""Apply G7 bootstrap settings after all upstream SWEET patches, before build.

This targets the pinned xnu-8796.141.3 tree. Missing anchors are fatal.
The original SWEET workflow never invokes this script.
"""
from pathlib import Path
import json
import sys

root = Path(sys.argv[1]).resolve()
pending = []

def edit(name, substitutions):
    path = root / name
    text = path.read_text()
    for old, new, count in substitutions:
        actual = text.count(old)
        if actual != count:
            raise SystemExit(f'{name}: expected {count} occurrences of {old!r}; found {actual}')
        text = text.replace(old, new)
    pending.append((path, text))

mapping = '\tstr\t\tx11, [x13, x12, lsl #TTE_SHIFT]\n'
second = "\t/* G7's 36 MiB splash reservation spans two 32 MiB blocks.\n\t * x10 below is the second aligned block, not the unaligned FB base. */\n\tMOV64\tx10, 0x9e000000\n\tMOV64\tx11, (ARM_TTE_TYPE_BLOCK | ARM_TTE_VALID | ARM_TTE_BLOCK_SH(SH_OUTER_MEMORY) | ARM_TTE_BLOCK_ATTRINDX(CACHE_ATTRINDX_WRITECOMB) | ARM_TTE_BLOCK_AF | ARM_TTE_BLOCK_PNX | ARM_TTE_BLOCK_NX)\n\torr\t\tx11, x11, x10\n\tadd\t\tx12, x12, #1\n\tstr\t\tx11, [x13, x12, lsl #TTE_SHIFT]\n"
edit('osfmk/arm64/start.s', [
    ('(0x9c000000 + 2368 * 4320)', '(0x9d400000 + 3088 * 5760)', 1),
    ('\tmov\t\tx4, #4320', '\tmov\t\tx4, #5760', 1),
    (mapping, mapping + second, 1),
])
edit('osfmk/arm64/sweet_early.c', [
    ('0x9c000000', '0x9d400000', 1),
    ('#define EARLY_WIDTH 1080u', '#define EARLY_WIDTH 1440u', 1),
    ('#define EARLY_HEIGHT 2400u', '#define EARLY_HEIGHT 3120u', 1),
    ('#define EARLY_STRIDE (4320u / 4)', '#define EARLY_STRIDE (5760u / 4)', 1),
    ('SWEET EARLY ', 'G7 EARLY ', 2),
])
edit('bsd/dev/sweet_ufs.c', [
    ('\tsweet_keys_init();', '\t/* G7 bring-up: SWEET key registers are not used. */', 1),
    ('\tsweet_touch_init();', '\t/* G7 bring-up: SWEET touch hardware is not used. */', 1),
    ('\tsweet_usb_probe();', '\t/* G7 bring-up: SWEET USB/PHY registers are not used. */', 1),
])
for path, text in pending:
    path.write_text(text)
print(json.dumps({'target': 'LG G7 ThinQ', 'xnu': '8796.141.3',
                  'splash': '0x9d400000', 'geometry': [1440, 3120, 5760],
                  'bootstrap_fb_blocks': ['0x9c000000', '0x9e000000'],
                  'device_drivers': 'SWEET input/USB probes disabled; no UFS node in G7 ADT'}, indent=2))
