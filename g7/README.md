# LG G7 ThinQ / SDM845 bring-up

Fork: https://github.com/WiziBox/ios-g7

## Verified 2026-10-28

The v2 display diagnostic executes on the LG G7. Windows fastboot reported
both image transfer and `Booting` OKAY; the user confirmed the display
alternates white and black. This proves ABL-to-shim execution and writes to
the FDT-validated splash reservation. **It does not prove XNU or iOS boot.**

Previous G7 code mixed the SWEET framebuffer address (`0x9c000000`) with
G7 hardware, packaged a raw Image despite stock using gzip+DTBs, and had
an empty ramdisk rather than an XNU payload. The old diagnostic intentionally
halted without visible output. These observations explain why a stationary
LG logo alone could not identify which stage failed; the exact cause of the
previous device failure was not independently recorded.

The supported build now uses a small display-only diagnostic, the stock
ARM64 text offset `0x80000`, boot header v1, stock header metadata/cmdline,
and the original three appended DTBs copied byte-for-byte from the stock
kernel. It never initializes UFS, GIC, or PSCI. Splash writes are allowed
only when the passed FDT contains the known fixed G7 reservation
`0x9d400000 + 0x2400000`; image/FDT overlap is rejected. Whole-region
monochrome output intentionally does not assume scanout pitch/pixel format.

## Build and inspect

Dependencies: Python 3, bash, gcc, aarch64-linux-gnu-gcc/binutils.
The local AOSP mkbootimg copy in `tools/` supports boot v1 without GKI tools.
The original phone dumps must exist locally at:

- `../dtb/g7/boot_unpacked/kernel`
- `../dtb/g7/boot_unpacked/header.txt`

Run from the repository root:

```sh
bash g7/build-g7.sh
python3 g7/tests/test_diag.py
```

The test also reads local `g7/live.dtb` and/or `dtb/g7/candidates/*.dtb`.
Output: `g7/shim/out/diag-v2/g7-diag-v2-boot.img` and `verification.json`.
The packer checks stock metadata, kernel/DTB round-trip, BSS/stack coverage,
ramdisk contents and the Android boot SHA1. Dumps and generated artifacts
are deliberately excluded from Git.

## Temporary device test

```sh
fastboot boot g7/shim/out/diag-v2/g7-diag-v2-boot.img
```

This is a temporary RAM boot. Do not flash this diagnostic. It loops without
servicing the bootloader watchdog; later reboot is possible. Hold power and
volume down to recover if needed, then select the usual boot mode.

## Remaining work toward iOS

1. Establish G7 scanout stride/format and show readable shim diagnostics.
2. Build a G7 XNU payload: replace SWEET early hardcoded framebuffer addresses,
   choose RAM from the real G7 map (SWEET default `0xb0000000` overlaps G7
   persistent RAM), and start with one CPU and no storage/touch drivers.
3. Verify XNU early boot and root-device detection before preparing userland.
4. Prepare and validate a compatible iOS root image; any destructive device
   partition operation requires separate user confirmation per `AGENTS.md`.

The other copied SWEET shim sources and `mkadt-g7.py` are incomplete porting
references. They are not used by the supported diagnostic build and are not
a validated G7 XNU configuration.
