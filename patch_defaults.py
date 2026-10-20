#!/usr/bin/env python3
"""Patch factory defaults of the GMKtec NucBox G3 Plus BIOS (G3_Plus_10W_SODIMM_20260112200632).

Only data is changed, no code: the default values of two AMI NVAR variables in the three
uncompressed StdDefaults copies (NVAR store + 2x 'NVRAM external defaults'). None of those
areas carry checksums (FFS attrib 0x00 -> fixed 0xAA data checksum, NVAR attrib 0x82) and the
image has no Boot Guard, so no checksum or signature has to be recomputed.

Usage:
    patch_defaults.py OFFICIAL.bin OUT.bin                     # unlock hidden menus only
    patch_defaults.py OFFICIAL.bin OUT.bin --max-mem-freq 2933 # + cap memory frequency
"""
import argparse
import hashlib

OFFICIAL_SHA256 = "85538d9c358fbb798f22e04616cb05b1b989b021c57992614d8143b8bf0e6073"

# Flash offset of each variable body in the 3 StdDefaults copies (found with UEFIExtract A75).
VARS = {
    "Setup": [0x6000B8, 0xF9B278, 0xFDB278],
    "SaSetup": [0x6011D5, 0xF9C395, 0xFDC395],
}
# JEDEC DDR4 speeds from 2133 up, as stored by the "Maximum Memory Frequency" menu
# (SaSetup 0x18B, u16, 0 = Auto; 2666 is stored as 2667).
MEM_FREQS = [2133, 2400, 2667, 2933, 3200]


def patches(max_mem_freq):
    # (variable, offset, size, expected official value, new value)
    p = [("Setup", 0x2F, 1, 0, 1)]  # show hidden menus (Chipset > System Agent > Memory Configuration, ...)
    if max_mem_freq:
        p.append(("SaSetup", 0x18B, 2, 0, max_mem_freq))  # Maximum Memory Frequency: Auto -> N
    return p


def targets(plist):
    for var, off, size, old, new in plist:
        for base in VARS[var]:
            yield base + off, size, old, new


def patch(data, plist):
    data = bytearray(data)
    assert hashlib.sha256(data).hexdigest() == OFFICIAL_SHA256, "not the expected official image"
    for pos, size, old, new in targets(plist):
        cur = int.from_bytes(data[pos:pos + size], "little")
        assert cur == old, f"{pos:#x}: expected {old}, found {cur}"
        data[pos:pos + size] = new.to_bytes(size, "little")
    return data


def check(orig, mod, plist):
    changed = [i for i in range(len(orig)) if orig[i] != mod[i]]
    allowed = {pos + i for pos, size, _, _ in targets(plist) for i in range(size)}
    assert changed and set(changed) <= allowed, f"unexpected bytes changed: {[hex(i) for i in changed]}"
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("official", help="official GMKtec bios.bin")
    ap.add_argument("out", help="output image")
    ap.add_argument("--max-mem-freq", type=int, choices=MEM_FREQS, metavar="MTS",
                    help="default Maximum Memory Frequency in MT/s (one of the menu values, e.g. 2933)")
    args = ap.parse_args()
    plist = patches(args.max_mem_freq)
    orig = open(args.official, "rb").read()
    mod = patch(orig, plist)
    changed = check(orig, mod, plist)
    open(args.out, "wb").write(mod)
    print(f"OK: {len(changed)} bytes changed at {[hex(i) for i in changed]}")
    print(f"sha256 {hashlib.sha256(mod).hexdigest()}  {args.out}")


if __name__ == "__main__":
    main()
