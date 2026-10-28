#!/usr/bin/env python3
from pathlib import Path
import struct
import sys
p = Path(sys.argv[1])
data = p.read_bytes()
if len(data) < 32 or struct.unpack_from('<III', data) != (0xfeedfacf, 0x0100000c, 0):
    raise SystemExit('Expected plain ARM64 Mach-O kernel (not arm64e)')
if b'G7 arm_init entered (MMU on)' not in data:
    raise SystemExit('Kernel lacks the G7 bootstrap patch; refusing to execute it')
print('Verified plain ARM64 kernel with G7 bootstrap marker')
