"""Part A miss analysis from corner_prune.py --pairs dumps (step 7, slim).

    .venv/bin/python scripts/prune_misses.py [--corners corners_derate_pvt_rcx]
        [--anchors fast_cb slow_cw] [--runs cross_dsplit_<a1>-<a2>_linear target_<a1>-<a2>]

For each result tag (default: the new-design and with-history configurations)
reads <tag>_misses.csv and <tag>_pairstats.csv and prints, per check:

- launch class: share of violating pairs and of missed pairs that are
  port-launched, and the miss rate per class;
- distance to g: share of missed and of all violating pairs within 5, 10 and
  20 ps of the guard band;
- scene: miss rate per target scene;
- scene level: share of missed pairs whose scene was skipped (violation misses);
- wasted pairs (flagged in scenes with no violations) by launch class and
  distance above g;
- path shift: median change in arrival and required time from the anchor that
  sets the base (the lower-slack anchor) to the target scene, for missed pairs
  against all violating pairs, by launch class. Arrival is the launch side
  (input delay or launch clock plus data path), required the capture side
  (capture clock plus setup/hold time and CRPR). Pair counts are summed over
  splits, so a pair missed in several splits counts each time.
"""

import argparse

import numpy as np
import pandas as pd

import corner_prune as cp

NEAR = {"[-5,0)": 5, "[-10,-5)": 10, "[-20,-10)": 20}


def pct(a, b):
    return 100 * a / b if b else np.nan


def class_table(stats):
    rows = []
    for check, s in stats.groupby("check"):
        n = s.pivot_table(index="launch", columns="kind", values="n", aggfunc="sum").fillna(0)
        n = n.reindex(columns=["viol", "miss", "wasted"], fill_value=0)
        for launch, r in n.iterrows():
            rows.append(dict(check=check, launch=launch, viol=int(r.viol), miss=int(r.miss),
                             share_of_viol=pct(r.viol, n.viol.sum()),
                             share_of_miss=pct(r.miss, n.miss.sum()),
                             miss_rate=pct(r.miss, r.viol)))
    return pd.DataFrame(rows).round(1)


def near_table(stats):
    rows = []
    for check, s in stats.groupby("check"):
        for kind in ("viol", "miss"):
            k = s[s.kind == kind]
            tot = k.n.sum()
            within = 0
            row = dict(check=check, kind=kind, n=int(tot))
            for b, ps in NEAR.items():
                within += k[k.gap_bin == b].n.sum()
                row[f"within_{ps}ps"] = pct(within, tot)
            rows.append(row)
    return pd.DataFrame(rows).round(1)


def scene_table(stats):
    t = stats.pivot_table(index=["check", "scene"], columns="kind", values="n", aggfunc="sum").fillna(0)
    t["miss_rate"] = 100 * t.miss / t.viol
    t["share_of_miss"] = 100 * t.miss / t.groupby("check").miss.transform("sum")
    return t[["viol", "miss", "miss_rate", "share_of_miss"]].round(1)


def wasted_table(stats):
    w = stats[stats.kind == "wasted"]
    t = w.pivot_table(index=["check", "launch"], columns="gap_bin", values="n", aggfunc="sum").fillna(0)
    order = [b for b in ("[0,5)", "[5,10)", "[10,20)", "[20,50)", "[50,inf)") if b in t]
    t = t[order]
    t.insert(0, "n", t.sum(axis=1))
    return t.astype(int)


def load_scenes(run):
    """Slack, arrival and required per (endpoint, check) at every scene of a run."""
    d = {s: pd.read_csv(cp.WORK / CORNERS / run / f"{s}_endpoints.csv").set_index(["endpoint", "check"])
         for s in cp.SCENES}
    return pd.concat({s: d[s][["slack_ps", "arrival_ps", "required_ps", "start_class"]] for s in cp.SCENES},
                     axis=1)


def shift_table(misses, runs):
    """Median arrival and required shift (scene - base anchor) for misses vs all violators."""
    a0, a1 = cp.ANCHORS
    frames = []
    for run in runs:
        w = load_scenes(run).dropna()
        first = w[(a0, "slack_ps")] <= w[(a1, "slack_ps")]
        base = {c: w[(a0, c)].where(first, w[(a1, c)]) for c in ("arrival_ps", "required_ps", "start_class")}
        launch = base["start_class"].replace("self", "reg")
        g = pd.Series(w.index.get_level_values("check"), index=w.index).map(cp.GUARD)
        m = misses[misses.run == run].groupby(["endpoint", "check", "scene"]).size()
        for s in cp.TARGETS:
            viol = w[(s, "slack_ps")] < g
            df = pd.DataFrame(dict(launch=launch[viol],
                                   d_arr=(w[(s, "arrival_ps")] - base["arrival_ps"])[viol],
                                   d_req=(w[(s, "required_ps")] - base["required_ps"])[viol]))
            df["missed"] = [m.get((e, c, s), 0) for e, c in df.index]
            frames.append(df.reset_index())
    df = pd.concat(frames, ignore_index=True)
    rows = []
    for (check, launch), d in df.groupby(["check", "launch"]):
        miss = d.loc[d.index.repeat(d.missed)]
        rows.append(dict(check=check, launch=launch,
                         viol_d_arr=d.d_arr.median(), viol_d_req=d.d_req.median(),
                         miss_n=len(miss), miss_d_arr=miss.d_arr.median(),
                         miss_d_req=miss.d_req.median()))
    return pd.DataFrame(rows).round(1)


def main():
    global CORNERS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corners", default="corners_derate_pvt_rcx", help="results dir under work/")
    ap.add_argument("--anchors", nargs=2, default=["fast_cb", "slow_cw"], metavar="SCENE")
    ap.add_argument("--runs", nargs="+", help="result tags (default: new design and with history)")
    args = ap.parse_args()
    CORNERS = args.corners
    cp.set_anchors(args.anchors)
    a = "-".join(args.anchors)
    tags = args.runs or [f"cross_dsplit_{a}_linear", f"target_{a}"]
    pd.set_option("display.width", 200)
    for tag in tags:
        d = cp.WORK / "prune" / args.corners
        misses = pd.read_csv(d / f"{tag}_misses.csv")
        stats = pd.read_csv(d / f"{tag}_pairstats.csv")
        print(f"===== {tag}: {stats.split.nunique()} splits, {stats.design.nunique()} designs")
        print("\nlaunch class (% of violating pairs, % of missed pairs, miss rate)")
        print(class_table(stats).to_string(index=False))
        print("\ndistance to g: % of pairs within 5 / 10 / 20 ps below g")
        print(near_table(stats).to_string(index=False))
        print("\nby scene")
        print(scene_table(stats).to_string())
        n_miss = len(misses)
        print(f"\nscene level: {pct((~misses.ran).sum(), n_miss):.2f}% of {n_miss} missed pairs "
              f"are in skipped scenes")
        print("\nwasted pairs (flagged in clean scenes) by distance above g, ps")
        print(wasted_table(stats).to_string())
        runs = sorted(misses.run.unique())
        print(f"\npath shift, scene - base anchor, ps (median; {len(runs)} runs with misses)")
        print(shift_table(misses, runs).to_string(index=False))
        print()


if __name__ == "__main__":
    main()
