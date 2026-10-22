"""Build scaled RC-corner SPEFs from one extracted SPEF.

    .venv/bin/python scripts/scale_spef.py <in.spef> [out_dir]

Writes <out_dir>/<stem>_<rc>.spef for every RC corner in RC_CORNERS (out_dir
defaults to the input's directory). Every resistance is scaled by the corner's
R factor; every capacitance (ground and coupling, and each net's total) by its
C factor. Scaling is unit-free, so the header units are copied unchanged.

This approximates multi-corner extraction from a single rule deck; the
factors are a disclosed assumption, not foundry data.
"""

import sys
from pathlib import Path

# rc corner -> (R factor, C factor)
RC_CORNERS = {
    "cw": (0.90, 1.10),   # C-worst: high C, low R
    "rcw": (1.10, 1.05),  # RC-worst: high R, slightly high C
    "cb": (1.10, 0.90),   # C-best: low C, high R
    "rcb": (0.90, 0.95),  # RC-best: low R, slightly low C
}


def scaled(line, factor):
    """Scale the last field of a SPEF value line."""
    head, value = line.rsplit(maxsplit=1)
    return f"{head} {float(value) * factor:.6g}\n"


def scale_spef(src, outs):
    """outs: list of (file, r_factor, c_factor), all written in one pass."""
    section = None
    with open(src) as f:
        for line in f:
            if line.startswith("*D_NET"):
                section = None
                for out, _, cf in outs:
                    out.write(scaled(line, cf))
                continue
            if line.startswith("*"):
                keyword = line.split(maxsplit=1)[0]
                if keyword in ("*CAP", "*RES"):
                    section = keyword
                elif keyword in ("*CONN", "*END", "*INDUC"):
                    section = None
            elif section and line.strip():
                for out, rf, cf in outs:
                    out.write(scaled(line, rf if section == "*RES" else cf))
                continue
            for out, _, _ in outs:
                out.write(line)


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {rc: out_dir / f"{src.stem}_{rc}.spef" for rc in RC_CORNERS}
    files = {rc: open(p, "w") for rc, p in paths.items()}
    try:
        scale_spef(src, [(files[rc], *RC_CORNERS[rc]) for rc in RC_CORNERS])
    finally:
        for f in files.values():
            f.close()
    for rc, p in paths.items():
        rf, cf = RC_CORNERS[rc]
        print(f"{rc}: R x{rf} C x{cf} -> {p}")


if __name__ == "__main__":
    main()
