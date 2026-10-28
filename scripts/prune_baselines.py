"""Part A baselines: heuristic scene pruning on the same runs as corner_prune.py.

    .venv/bin/python scripts/prune_baselines.py [--corners corners_derate]
        [--anchors fast_cb slow_rcw] [--designs aes,ibex,...]
        [--guard-setup 0] [--guard-hold 40]

Every method runs the two anchors plus its own scene choice, per test run:

- physics: the anchors only (slowest scene for setup, fastest for hold).
- dominance_history: every scene that was some violating endpoint's worst in
  the design's other runs (leave-one-run-out, so it sees more history than
  target-mode calibration's k runs).
- dominance_cross: every scene that was some violating endpoint's worst in the
  other designs.
- oracle: exactly the scenes with violations (the ceiling).

A pair violates if its slack is below the guard band g (--guard-setup,
--guard-hold; default corner_prune.GUARD, tagged _g<setup>-<hold> otherwise).
viol_<check> is the share of violating pairs in scenes that run, which is also
the pair recall since a heuristic flags whole scenes; ep_<check> is the share
of violating endpoints caught in at least one scene that runs. saved is
1 - (scenes run) / (all 12 scenes) in measured STA runtime. Per-run results go
to work/prune/[<corners>/]baselines[_<a1>-<a2>].csv, laid out like
corner_prune.py's; the summary prints the mean per held-out design.
"""

import argparse

import numpy as np
import pandas as pd

import corner_prune as cp


def scene_slack(df):
    """Slack of every endpoint (rows of df) at all 12 scenes."""
    s = df[cp.TARGETS].copy()
    for a in cp.ANCHORS:
        s[a] = df[f"{a}_slack_ps"]
    return s[cp.SCENES]


def score_run(d, slack, keep, runtime):
    viol = slack.lt(d.g, axis=0)
    kept = viol[sorted(keep)]
    res = dict(skipped=1 - len(keep) / len(cp.SCENES),
               saved=1 - runtime[sorted(keep)].sum() / runtime.sum())
    for check in cp.CHECKS:
        rows = (d.check == check).values
        n = viol[rows].values.sum()
        n_ep = viol[rows].any(axis=1).sum()
        res[f"viol_{check}"] = kept[rows].values.sum() / n if n else np.nan
        res[f"ep_{check}"] = kept[rows].any(axis=1).sum() / n_ep if n_ep else np.nan
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corners", default="corners_derate", help="results dir under work/")
    ap.add_argument("--anchors", nargs=2, choices=cp.SCENES, default=list(cp.ANCHORS),
                    metavar="SCENE", help="the two anchor scenes (default fast_cb slow_rcw)")
    ap.add_argument("--designs", help="comma-separated design pool (default: all)")
    ap.add_argument("--guard-setup", type=float, default=cp.GUARD["setup"], help="g for setup (ps)")
    ap.add_argument("--guard-hold", type=float, default=cp.GUARD["hold"], help="g for hold (ps)")
    args = ap.parse_args()
    default_anchors = args.anchors == list(cp.ANCHORS)
    cp.set_anchors(args.anchors)
    guard = {"setup": args.guard_setup, "hold": args.guard_hold}
    default_guard = guard == cp.GUARD
    cp.GUARD.update(guard)
    designs = args.designs.split(",") if args.designs else None

    df = cp.load(args.corners, designs)
    runtime = cp.load_runtime(args.corners)
    slack = scene_slack(df)
    viol = slack.lt(df.g, axis=0)
    worst = slack.idxmin(axis=1).where(viol.any(axis=1))
    anchors = set(cp.ANCHORS)

    rows = []
    for run, d in df.groupby("run"):
        design = d.design.iloc[0]
        dirty = set(viol.loc[d.index].columns[viol.loc[d.index].any()])
        choices = {
            "physics": anchors,
            "dominance_history": anchors | set(worst[(df.design == design) & (df.run != run)].dropna()),
            "dominance_cross": anchors | set(worst[df.design != design].dropna()),
            "oracle": anchors | dirty,
        }
        for method, keep in choices.items():
            rows.append(dict(design=design, run=run, method=method,
                             **score_run(d, slack.loc[d.index], keep, runtime.loc[run])))
    res = pd.DataFrame(rows)

    tag = ("baselines" + ("" if default_anchors else "_" + "-".join(args.anchors))
           + ("" if default_guard else f"_g{args.guard_setup:g}-{args.guard_hold:g}"))
    out = cp.WORK / "prune" / f"{tag}.csv"
    if args.corners != "corners_derate":
        out = cp.WORK / "prune" / args.corners / f"{tag}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)

    cols = ["skipped", "saved", "viol_setup", "viol_hold", "ep_setup", "ep_hold"]
    table = res.groupby(["method", "design"])[cols].mean().mul(100).round(1)
    pd.set_option("display.width", 250)
    print(f"{tag} ({args.corners}), anchors {' '.join(cp.ANCHORS)}")
    print(table.to_string())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
