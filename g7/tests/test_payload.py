#!/usr/bin/env python3
"""Run the actual C loader validator against valid and corrupt payloads."""
from pathlib import Path
import ctypes
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VIRT = 0xfffffe0006000000

def fixture():
    data = bytearray(0x340)
    struct.pack_into('<8sII7Q', data, 0, b'SWEETXNU', 1, 2,
                     VIRT, VIRT + 0x1000000, 0x320, 16, VIRT + 0x1008000,
                     0xb4000000, 0x49f00000)
    struct.pack_into('<4Q', data, 0x2a8, VIRT + 0x1000000, 0x4000, 0x300, 8)
    struct.pack_into('<4Q', data, 0x2c8, VIRT + 0x1004000, 0x4000, 0x310, 8)
    return data

with tempfile.TemporaryDirectory(prefix='g7-payload-test-') as td:
    libfile = Path(td) / 'payload.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(ROOT / 'g7/shim/payload.c'), '-o', str(libfile)], check=True)
    lib = ctypes.CDLL(str(libfile))
    fn = lib.g7_payload_check
    fn.restype = ctypes.c_char_p
    fn.argtypes = [ctypes.c_void_p] + [ctypes.c_uint64] * 6
    def check(data, available=None, rd=0xa1000000, shim=0x80080000, dtb=0x83000000):
        buf = ctypes.create_string_buffer(bytes(data))
        return fn(buf, len(data) if available is None else available,
                  rd, rd + len(data), shim, shim + 0x20000, dtb)
    valid = fixture()
    assert check(valid) is None
    for n in [0, 1, 0x2a7]:
        assert check(valid, available=n), n
    cases = [
        ('segment count zero', 12, '<I', 0),
        ('segment count excessive', 12, '<I', 33),
        ('wrong version', 8, '<I', 2),
        ('wrong physical base', 0x38, '<Q', 0xb0000000),
        ('wrong memory size', 0x40, '<Q', 0xffffffff),
        ('virtual overflow', 0x10, '<Q', 0xffffffffffff0000),
        ('entry outside RAM', 0x18, '<Q', 0),
        ('entry in BSS', 0x18, '<Q', VIRT + 0x1000100),
        ('ADT beyond input', 0x20, '<Q', 0x100000000),
        ('unaligned ADT', 0x20, '<Q', 0x321),
        ('oversize ADT', 0x28, '<Q', 0x100001),
        ('kernel end below base', 0x30, '<Q', VIRT - 1),
        ('no room for boot args', 0x30, '<Q', VIRT + 0x49f00000),
        ('file size exceeds VM', 0x2c0, '<Q', 0x10000),
        ('file outside input', 0x2b8, '<Q', 0x100000000),
        ('file in header', 0x2b8, '<Q', 0),
        ('unaligned file', 0x2b8, '<Q', 0x301),
        ('unaligned VM', 0x2a8, '<Q', VIRT + 0x1000001),
        ('overlapping segments', 0x2c8, '<Q', VIRT + 0x1000000),
        ('segment beyond kernel end', 0x2c8, '<Q', VIRT + 0x1008000),
        ('file points into ADT', 0x2b8, '<Q', 0x328),
    ]
    for name, offset, fmt, value in cases:
        bad = bytearray(valid)
        struct.pack_into(fmt, bad, offset, value)
        assert check(bad), name
    bad = bytearray(valid)
    bad[0] = 0
    assert check(bad), 'bad magic'
    bad = bytearray(valid)
    bad[0x48:0x2a8] = b'x' * 608
    assert check(bad), 'unterminated command line'
    assert check(valid, rd=0xb4000000), 'initrd overlaps kernel'
    assert check(valid, shim=0xb4000000), 'shim overlaps kernel'
    assert check(valid, dtb=0xb4000000), 'FDT overlaps kernel'
    if len(sys.argv) > 1:
        assert check(Path(sys.argv[1]).read_bytes()) is None, 'real kernel payload'
print('PASS: actual C validator accepts valid payloads and rejects 29 malformed/bounds cases')
