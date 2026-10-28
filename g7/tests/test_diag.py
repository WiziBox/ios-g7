from pathlib import Path
import ctypes
import importlib.util
import random
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='g7-test-') as td:
    libpath = Path(td) / 'splash.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(root / 'g7/shim/splash.c'), '-o', str(libpath)], check=True)
    lib = ctypes.CDLL(str(libpath))
    fn = lib.g7_splash_region
    fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                   ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
    def check(data):
        buffer = ctypes.create_string_buffer(data)
        base, size = ctypes.c_uint64(), ctypes.c_uint64()
        ok = fn(buffer, len(data), ctypes.byref(base), ctypes.byref(size))
        if ok:
            assert (base.value, size.value) == (0x9d400000, 0x2400000)
        return ok
    paths = [root / 'g7/live.dtb'] + sorted((root / 'dtb/g7/candidates').glob('*.dtb'))
    paths = [p for p in paths if p.exists()]
    if not paths: raise SystemExit('Local G7 DTB dumps required; see g7/README.md')
    for path in paths:
        data = path.read_bytes()
        assert check(data), path
        for n in [0, 1, 39, 40, 256, len(data) - 1]:
            assert not check(data[:n]), (path, n)
        for field in [4, 8, 12, 32, 36]:
            bad = bytearray(data)
            struct.pack_into('>I', bad, field, 0xffffffff)
            assert not check(bytes(bad)), (path, field)
        bad = data.replace(b'cont_splash_region@9d400000', b'cont_splash_region@9c000000')
        assert not check(bad)
        bad = data.replace(struct.pack('>4I', 0, 0x9d400000, 0, 0x2400000),
                           struct.pack('>4I', 0, 0x9c000000, 0, 0x2400000))
        assert not check(bad)
    rng = random.Random(710)
    data = paths[0].read_bytes()
    for i in range(1000):
        bad = bytearray(data)
        for j in range(rng.randrange(1, 8)):
            bad[rng.randrange(len(bad))] = rng.randrange(256)
        check(bytes(bad))

spec = importlib.util.spec_from_file_location('pack_diag', root / 'g7/pack-diag.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for data in [b'', b'not gzip', b'\x1f\x8b']:
    try:
        module.stock_parts(data)
    except Exception:
        pass
    else:
        raise AssertionError('Malformed kernel accepted')
print('PASS: 4 real FDTs, truncated/invalid bounds and wrong splash addresses, 1000 mutated FDTs, malformed kernels')
