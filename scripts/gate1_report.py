"""Aggregate Gate 1 results from work/gate1/ into a summary table.

    .venv/bin/python scripts/gate1_report.py

Pairs each target's hold_only (H0) and setup_then_hold (H1) runs and reports
the counterfactual induced share, per-buffer attribution, hold-margin erosion
during setup repair and residual hold violations. Writes
work/gate1/summary.csv and prints a markdown table.
"""

import csv
import json
import os
from pathlib import Path

WORK = Path(os.environ.get("WORK_HOME", Path(__file__).resolve().parents[1] / "work"))
GATE1 = WORK / "gate1"
# Endpoints with checkpoint hold slack below this are "near-critical" (ps).
NEAR_CRITICAL_PS = 50.0
UNCONSTRAINED_PS = 1e6


def load(design, variant, mode):
    path = GATE1 / f"{design}_{variant}_{mode}.json"
    return json.loads(path.read_text()) if path.exists() else None


def worst_hold(state):
    return min(c["hold_wns"] for c in state["corners"].values())


def hold_viol(state):
    return sum(c["hold_viol"] for c in state["corners"].values())


def endpoint_erosion(design, variant):
    """Hold-slack loss during setup repair, from the endpoints CSV."""
    path = GATE1 / f"{design}_{variant}_setup_then_hold_endpoints.csv"
    decreased = 0
    loss_near = 0.0
    near = 0
    with path.open() as f:
        for row in csv.DictReader(f):
            h0, h1 = float(row["hold_ckpt"]), float(row["hold_setup"])
            if abs(h0) > UNCONSTRAINED_PS or abs(h1) > UNCONSTRAINED_PS:
                continue
            if h1 < h0 - 1e-3:
                decreased += 1
            if h0 < NEAR_CRITICAL_PS:
                near += 1
                loss_near += max(0.0, h0 - h1)
    return decreased, near, loss_near


def summarize(design, variant):
    a = load(design, variant, "hold_only")
    b = load(design, variant, "setup_then_hold")
    if a is None or b is None:
        return None
    h0, h1 = a["hold_buffers"], b["hold_buffers"]
    induced_n = h1["count"] - h0["count"]
    induced_area = h1["area_um2"] - h0["area_um2"]
    moves = b["setup_moves"]
    attr = b["attribution"]
    classes = attr["buffers_by_class"]
    decreased, near, loss_near = endpoint_erosion(design, variant)
    to_slvt = sum(n for k, n in moves["vt_transitions"].items() if k.endswith("->SL"))
    return {
        "design": design,
        "variant": variant,
        "period_ps": int(b["clock_period_ps"]),
        "setup_wns_ckpt": b["checkpoint"]["corners"]["slow"]["setup_wns"],
        "setup_wns_after": b["after_setup"]["corners"]["slow"]["setup_wns"],
        "setup_viol_after": b["after_setup"]["corners"]["slow"]["setup_viol"],
        "moves": moves["total"],
        "moves_size_only": moves["size_only"],
        "moves_vt_only": moves["vt_only"],
        "moves_both": moves["both"],
        "moves_to_slvt": to_slvt,
        "setup_delta_area_um2": moves["delta_area_um2"],
        "H0_count": h0["count"],
        "H0_area_um2": h0["area_um2"],
        "H1_count": h1["count"],
        "H1_area_um2": h1["area_um2"],
        "induced_count": induced_n,
        "induced_area_um2": round(induced_area, 3),
        "induced_share_area": round(induced_area / h1["area_um2"], 3) if h1["area_um2"] > 0 else None,
        "buf_pre_existing": classes["pre_existing"]["count"],
        "buf_induced": classes["induced"]["count"],
        "buf_later": classes["later"]["count"],
        "buf_unmapped": classes["unmapped"]["count"],
        "induced_endpoints": attr["induced_endpoints"],
        "induced_endpoints_with_moved_cell": attr["induced_endpoints_with_moved_cell"],
        "eroded_endpoints": attr["eroded_endpoints"],
        "endpoints_hold_decreased": decreased,
        "near_critical_endpoints": near,
        "near_critical_hold_loss_ps": round(loss_near, 3),
        "hold_wns_ckpt": worst_hold(b["checkpoint"]),
        "hold_wns_after_setup": worst_hold(b["after_setup"]),
        "residual_hold_viol_A": hold_viol(a["after_hold"]),
        "residual_hold_viol_B": hold_viol(b["after_hold"]),
        "setup_s": b["runtime_s"]["setup"],
        "hold_s_A": a["runtime_s"]["hold"],
        "hold_s_B": b["runtime_s"]["hold"],
    }


def main():
    targets = sorted({
        tuple(p.name.split("_hold_only.json")[0].rsplit("_", 1))
        for p in GATE1.glob("*_hold_only.json")
    })
    rows = [r for d, v in targets if (r := summarize(d, v))]
    rows.sort(key=lambda r: (r["design"], r["variant"].rstrip("0123456789"), r["period_ps"]))
    if not rows:
        raise SystemExit(f"no paired Gate 1 results in {GATE1}")

    with (GATE1 / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    cols = [
        ("design", "design"), ("variant", "variant"),
        ("setup_wns_ckpt", "setup WNS ckpt"), ("setup_wns_after", "after setup"),
        ("moves", "moves"), ("moves_to_slvt", "→SL"),
        ("hold_wns_ckpt", "hold WNS ckpt"), ("hold_wns_after_setup", "after setup"),
        ("endpoints_hold_decreased", "EPs hold ↓"), ("near_critical_hold_loss_ps", "near-crit loss ps"),
        ("induced_endpoints", "induced EPs"), ("H0_count", "H0"), ("H1_count", "H1"),
        ("induced_count", "H1−H0"), ("induced_share_area", "share (area)"),
        ("buf_induced", "bufs→induced EP"), ("residual_hold_viol_B", "resid hold B"),
        ("setup_s", "setup s"),
    ]
    print("| " + " | ".join(h for _, h in cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join("–" if r[k] is None else str(r[k]) for k, _ in cols) + " |")
    print(f"\nwrote {GATE1 / 'summary.csv'}")


if __name__ == "__main__":
    main()
