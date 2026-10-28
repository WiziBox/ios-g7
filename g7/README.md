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

1. G7 text diagnostic verified: 1440x3120 with 5760-byte pitch is readable.
   Channel order remains unverified; black/white text does not establish it.
2. Build a G7 XNU payload (in progress): replace SWEET early hardcoded framebuffer addresses,
   choose RAM from the real G7 map (SWEET default `0xb0000000` overlaps G7
   persistent RAM), and start with one CPU and no storage/touch drivers.
3. Verify XNU early boot and root-device detection before preparing userland.
4. Prepare and validate a compatible iOS root image; any destructive device
   partition operation requires separate user confirmation per `AGENTS.md`.

`mkadt-g7.py` now builds an early G7 tree with one CPU, no UFS node, and
RAM `0xb4000000..0xfe000000` (top 1 MiB reserved for panic logs). Kernel patch
`0082-g7-bootstrap-display.patch` maps both 32 MiB blocks crossed by the G7
splash buffer and adjusts the early console. The inherited `xnu` Actions
workflow builds this patch; the output retains the SWEET kernel filename
because it reuses that machine configuration. This kernel is not yet
verified on the G7. `configure-xnu.py` can reproduce the patch on an upstream
tree after patches 0001..0081; do not run it after patch 0082.

The copied full SWEET shim sources remain incomplete porting references.
The supported default build still makes only the diagnostic.


## XNU loader (early bring-up, no root filesystem yet)

The loader checks every segment before any kernel writes, forbids overlap
with the shim/FDT/initrd, requires the G7 RAM configuration, and reports
exceptions on screen. The actual C validator is exercised with 29 negative
cases plus valid generated and real payloads:

~~~sh
python3 g7/tests/test_payload.py
bash g7/build-xnu-boot.sh G7_KERNEL
~~~

It refuses an arm64e kernel or a kernel without the retained G7 arm_init
marker. For validating the loader with a reference kernel without executing it:

~~~sh
bash g7/build-xnu-boot.sh --stage-only REFERENCE_KERNEL
~~~

The stage-only image was verified on hardware: STOP displayed
STAGED ONLY; XNU NOT EXECUTED. Patch 0083 additionally maps both final
TTBR1 framebuffer blocks and relocates the console by the G7's 20-MiB
offset into the first block. Actual XNU execution is not yet verified.
