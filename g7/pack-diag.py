#!/usr/bin/env python3
"""Mirror the stock G7 v1 boot header and gzip+DTB kernel container."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parent.parent

def stock_parts(data):
    stream = zlib.decompressobj(31)
    image = stream.decompress(data)
    if not stream.eof or image[56:60] != b'ARMd':
        raise ValueError('Stock kernel must be gzip-compressed ARM64 Image')
    tail = stream.unused_data
    pos = 0
    count = 0
    while pos < len(tail):
        if len(tail) - pos < 40 or tail[pos:pos+4] != b'\xd0\x0d\xfe\xed':
            raise ValueError('Invalid appended stock DTB')
        size = struct.unpack_from('>I', tail, pos + 4)[0]
        if size < 40 or size > len(tail) - pos:
            raise ValueError('Invalid stock DTB size')
        pos += size
        count += 1
    if count != 3:
        raise ValueError(f'Expected 3 stock G7 DTBs, found {count}')
    return image, tail

def verify(boot, image, tail, meta, ramdisk):
    if boot[:8] != b'ANDROID!': raise ValueError('Bad Android magic')
    ks, ka, rs, ra, ss, sa, ta, page, version, osv = struct.unpack_from('<10I', boot, 8)
    expected = (int(meta['kernel_addr'], 0), int(meta['ramdisk_addr'], 0),
                int(meta['tags_addr'], 0), int(meta['page_size']),
                int(meta['header_version']), int(meta['os_version'], 0))
    if (ka, ra, ta, page, version, osv) != expected or ss or sa:
        raise ValueError('Stock header mismatch')
    if page != 4096 or version != 1: raise ValueError('Expected G7 boot v1')
    if struct.unpack_from('<I', boot, 1644)[0] != 1648:
        raise ValueError('Bad v1 header size')
    cmdline = boot[64:576].split(b'\0')[0] + boot[608:1632].split(b'\0')[0]
    if cmdline.decode() != meta['cmdline'] or rs != len(ramdisk):
        raise ValueError('Stock command line or ramdisk size mismatch')
    kernel = boot[page:page+ks]
    restored, dtbs = stock_parts(kernel)
    if restored != image or dtbs != tail: raise ValueError('Kernel round-trip failed')
    if len(image) != struct.unpack_from('<Q', image, 16)[0]:
        raise ValueError('ARM64 image_size does not cover BSS/stacks')
    offset = page + (ks + page - 1) // page * page
    if boot[offset:offset+rs] != ramdisk: raise ValueError('Ramdisk mismatch')
    sha = hashlib.sha1()
    for payload in (kernel, ramdisk, b'', b''):
        sha.update(payload)
        sha.update(struct.pack('<I', len(payload)))
    if boot[576:596] != sha.digest(): raise ValueError('Android boot SHA1 mismatch')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--name', default='g7-diag-v2-boot')
    parser.add_argument('--kind', default='display-only diagnostic, not iOS')
    parser.add_argument('--ramdisk', type=Path)
    args = parser.parse_args()
    if '/' in args.name or '\\' in args.name: parser.error('name must be a basename')
    out = args.out.resolve()
    stock = ROOT / 'dtb/g7/boot_unpacked'
    stock_image, tail = stock_parts((stock / 'kernel').read_bytes())
    meta = dict(line.split(': ', 1) for line in (stock / 'header.txt').read_text().splitlines())
    image = (out / 'Image').read_bytes()
    if image[8:16] != stock_image[8:16] or image[24:32] != stock_image[24:32]:
        raise ValueError('ARM64 load offset/flags must match stock G7')
    kernel = gzip.compress(image, compresslevel=9, mtime=0) + tail
    (out / 'Image.gz-dtb').write_bytes(kernel)
    # A valid minimal newc archive, reproducible and intentionally not an iOS payload.
    cpio = b'070701' + b''.join(f'{v:08x}'.encode() for v in
        (0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 11, 0)) + b'TRAILER!!!\0'
    cpio += b'\0' * (-len(cpio) % 4)
    ramdisk = args.ramdisk.read_bytes() if args.ramdisk else gzip.compress(cpio, mtime=0)
    (out / 'ramdisk.cpio.gz').write_bytes(ramdisk)
    osv = int(meta['os_version'], 0)
    os_version = '.'.join(str((osv >> shift) & 127) for shift in (25, 18, 11))
    patch = f'{2000 + ((osv >> 4) & 127):04d}-{osv & 15:02d}'
    destination = out / (args.name + '.img')
    subprocess.run([sys.executable, str(ROOT / 'g7/tools/mkbootimg'), '--header_version', '1',
        '--kernel', str(out / 'Image.gz-dtb'), '--ramdisk', str(out / 'ramdisk.cpio.gz'),
        '--base', '0', '--kernel_offset', meta['kernel_addr'],
        '--ramdisk_offset', meta['ramdisk_addr'], '--tags_offset', meta['tags_addr'],
        '--pagesize', meta['page_size'], '--os_version', os_version,
        '--os_patch_level', patch, '--cmdline', meta['cmdline'],
        '-o', str(destination)], check=True)
    verify(destination.read_bytes(), image, tail, meta, ramdisk)
    report = {'image': destination.name, 'kind': args.kind,
              'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'stock_dtbs_preserved': 3, 'arm64_text_offset': hex(struct.unpack_from('<Q', image, 8)[0]),
              'boot_header_version': 1, 'verified': True}
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
