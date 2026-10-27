"""Write one OpenRCX rules file per RC corner from the stock ASAP7 rules.

    .venv/bin/python scripts/rcx_corner_rules.py [out_dir]

Writes <out_dir>/<rc>.rules for every RC corner (out_dir defaults to
$WORK_HOME/rcx). Every table row of the stock file is "spacing coupling_C
ground_C R" (RESOVER rows are "spacing spacing 0 R"); each row is scaled by
the factors of the metal layer the table belongs to. Via resistance comes from
the LEF and is unchanged.

The factors come from a geometric model of +-3 sigma back-end variation, not
foundry data. Each layer has width w and spacing s = w (pitch 2w, ASAP7 tech
LEF), thickness t and dielectric height h:

    R  ~ 1 / (w t)        coupling C ~ t / s        ground C ~ w / h

ASAP7 has no BEOL variation data, so all three magnitudes are imported
(sources in references.md, BEOL variation):

- Width: 3 sigma CD 2.7 nm on every layer, the IRDS 2021 metal CD control at
  18 nm half pitch (Table LITH-1). Upper layers keep the same absolute CD, an
  extrapolation, so thin lower metals vary more than thick upper ones.
- Thickness: +-10% on every layer, the ITRS 2007 Cu erosion thinning target
  (10% of height, Table INTC2b), applied symmetrically; sigma not stated.
- Dielectric height: +-5%, no published value found (uncited assumption).

A wider line narrows the space to its neighbour, so coupling C moves more than
ground C. Corner geometry follows the foundry-derived definitions in Chan,
Dobre & Kahng (ICCD 2014); every parameter sits at +-3 sigma together, which
is pessimistic against statistical corners. Corners:

    cw   wide, thick metal, thin dielectric    R down, C up
    rcw  narrow, thin metal, thin dielectric   R up, coupling C down
    cb   narrow, thin metal, thick dielectric  R up, C down
    rcb  wide, thick metal, thick dielectric   R down, coupling C up
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "third_party/OpenROAD-flow-scripts/flow/platforms/asap7/rcx_patterns.rules"
WORK = Path(os.environ.get("WORK_HOME", ROOT / "work"))

# OpenRCX metal index -> drawn width (nm): M1-M9, then Pad
WIDTH_NM = {1: 18, 2: 18, 3: 18, 4: 24, 5: 24, 6: 32, 7: 32, 8: 40, 9: 40, 10: 40}
CD_3SIGMA_NM = 2.7
THICKNESS_3SIGMA = 0.10
ILD_3SIGMA = 0.05

# rc corner -> (sign of width/thickness change, sign of dielectric height change)
RC_CORNERS = {"cw": (1, -1), "rcw": (-1, -1), "cb": (-1, 1), "rcb": (1, 1)}


def factors(width_nm, geo, ild):
    """(R, coupling C, ground C) factors for one layer at one corner; s = w nominally."""
    w = 1 + geo * CD_3SIGMA_NM / width_nm
    t = 1 + geo * THICKNESS_3SIGMA
    s = 2 - w
    h = 1 + ild * ILD_3SIGMA
    return 1 / (w * t), t / s, w / h


def scaled(line, f, kind):
    v = [float(x) for x in line.split()]
    r, cc, cg = f
    if kind == "res":
        v[3] *= r
    elif kind == "diag":   # diagonal coupling sits in the third column
        v[2] *= cc
        v[3] *= r
    else:
        v[1] *= cc
        v[2] *= cg
        v[3] *= r
    return " ".join(f"{x:.6g}" for x in v) + "\n"


def write_rules(src, outs):
    """outs: list of (file, {metal: factors}), all written in one pass."""
    metal = kind = None
    with open(src) as f:
        for line in f:
            tok = line.split()
            if tok and tok[0] == "Metal":
                metal = int(tok[1])
                kind = "res" if "RESOVER" in tok else "diag" if "DIAGUNDER" in tok else "cap"
            elif len(tok) == 4 and tok[0][0].isdigit():
                for out, fac in outs:
                    out.write(scaled(line, fac[metal], kind))
                continue
            for out, _ in outs:
                out.write(line)


def main():
    if len(sys.argv) > 2:
        sys.exit(__doc__)
    out_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else WORK / "rcx"
    out_dir.mkdir(parents=True, exist_ok=True)
    fac = {rc: {m: factors(w, *signs) for m, w in WIDTH_NM.items()}
           for rc, signs in RC_CORNERS.items()}
    paths = {rc: out_dir / f"{rc}.rules" for rc in RC_CORNERS}
    files = {rc: open(p, "w") for rc, p in paths.items()}
    try:
        write_rules(STOCK, [(files[rc], fac[rc]) for rc in RC_CORNERS])
    finally:
        for f in files.values():
            f.close()
    print("rc   layer  R      Cc     Cg")
    for rc in RC_CORNERS:
        for m in (1, 4, 6, 8):
            print(f"{rc:4s} M{m:<5d}" + " ".join(f"{x:.3f}" for x in fac[rc][m]))
    for rc, p in paths.items():
        print(f"{rc} -> {p}")


if __name__ == "__main__":
    main()
