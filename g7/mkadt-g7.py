#!/usr/bin/env python3
"""G7 early-boot ADT: one CPU, FDT-verified display, no storage or input."""
from pathlib import Path
import argparse
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import adt
import mkadt

PHYS_BASE = 0xb4000000
MEM_SIZE = 0x4a000000
FB_BASE, FB_SIZE = 0x9d400000, 0x2400000
WIDTH, HEIGHT, STRIDE = 1440, 3120, 5760

def build():
    # The G7 iomem dump has contiguous System RAM b3800000..17df9ffff.
    # Use a 32-MiB-aligned subset below 4G for the existing bootstrap tables;
    # never use SWEET's b0000000 (G7 ramoops) or its larger upper-bank size.
    mkadt.PHYS_BASE, mkadt.MEM_SIZE = PHYS_BASE, MEM_SIZE
    mkadt.FB, mkadt.FB_SIZE = FB_BASE, FB_SIZE
    mkadt.FB_W, mkadt.FB_H, mkadt.FB_STRIDE = WIDTH, HEIGHT, STRIDE
    tree = mkadt.build()
    tree.children = [c for c in tree.children if c.name != 'sweet-ufs']
    cpus = next(c for c in tree.children if c.name == 'cpus')
    cpus.children = cpus.children[:1]
    for child in tree.children:
        if child.name == 'chosen':
            child.props = [(k, f, b'g7-shim\0' if k in ('firmware-version', 'system-firmware-version') else v)
                           for k, f, v in child.props]
    tree.props = [(k, f, v + b'lg,judyln\0qcom,sdm845\0' if k == 'compatible' else v)
                  for k, f, v in tree.props]
    return tree

def verify(tree):
    chosen = next(c for c in tree.children if c.name == 'chosen')
    base = struct.unpack('<Q', chosen.prop('dram-base'))[0]
    size = struct.unpack('<Q', chosen.prop('dram-size'))[0]
    assert base == PHYS_BASE and size == MEM_SIZE - mkadt.PANIC_LOG_SIZE
    assert base >= 0xb3800000 and base + MEM_SIZE <= 0x17dfa0000
    assert not any(c.name == 'sweet-ufs' for c in tree.children)
    assert len(next(c for c in tree.children if c.name == 'cpus').children) == 1
    fb = next(c for c in tree.children if c.name == 'sweet-fbcon')
    assert struct.unpack('<QQ', fb.prop('reg')) == (FB_BASE, FB_SIZE)
    assert STRIDE * HEIGHT <= FB_SIZE

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    tree = build()
    verify(tree)
    blob = adt.serialize(tree)
    restored, end = adt.parse(blob)
    assert end == len(blob)
    verify(restored)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes, one CPU, RAM {PHYS_BASE:#x}, no UFS')
