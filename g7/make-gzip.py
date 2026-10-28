from pathlib import Path
import gzip
import sys

base = Path(sys.argv[1])
shim = (base / "diag/Image").read_bytes()
dtbs = (base / "g7-dtb-bundle.bin").read_bytes()

compressed = gzip.compress(shim, compresslevel=9, mtime=0)

target = base / "diag/Image-g7-gzip-dtb"
target.write_bytes(compressed + dtbs)

assert gzip.decompress(compressed) == shim

print("Shim:", len(shim))
print("Compressed:", len(compressed))
print("DTBs:", len(dtbs))
print("Final:", target.stat().st_size)