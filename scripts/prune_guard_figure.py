"""Part A figure: compute saved vs hold guard band, pruner vs heuristics.

    .venv/bin/python scripts/prune_guard_figure.py [--corners corners_derate_pvt_rcx]
        [--anchors fast_cb slow_cw] [--guards 10 15 ... 50] [--k 3] [--theme dark|light]

Reads, from work/prune/<corners>/, one result per g_hold (g_setup = 0, α = 1%;
files for the default g_hold = 40 are untagged, the others tagged _g0-<g>):

- new design: corner_prune.py cross --cal-split design --model linear --guard-hold g;
- with history: corner_prune.py target --guard-hold g (LightGBM), at --k
  calibration runs (default 3, the largest k every design has runs for);
- heuristics and oracle: prune_baselines.py --guard-hold g.

Each point is the mean over held-out designs of per-design means; a panel
averages the baselines over the same designs as its pruner results. A hollow
marker means some split (pruner) or run (heuristic) caught < 99% of the
violating pairs of a check. Writes work/figures/guard.png, .svg and .csv (dark
theme by default, for slides).
"""

import argparse

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

import corner_prune as cp  # noqa: E402
import prune_figure as pf  # noqa: E402

METHODS = ("pruner", "physics", "dominance")
SAFE = 0.99


def gtag(g):
    return "" if g == cp.GUARD["hold"] else f"_g0-{g:g}"


def points(df, method):
    """Mean saved over designs, and whether every split or run caught >= SAFE in both checks."""
    per = df.groupby("design").saved.mean()
    worst = df[["viol_setup", "viol_hold"]].min(axis=1).min()
    return dict(method=method, saved=100 * per.mean(), worst=100 * worst, safe=worst >= SAFE,
                designs=list(per.index))


def load(d, a, guards, k):
    rows = []
    for g in guards:
        base = pd.read_csv(d / f"baselines_{a}{gtag(g)}.csv")
        new = pd.read_csv(d / f"cross_dsplit_{a}{gtag(g)}_linear.csv")
        hist = pd.read_csv(d / f"target_{a}{gtag(g)}.csv")
        hist = hist[hist.k == k]
        for panel, res, heur in (("new design", new, "dominance_cross"),
                                 ("with history", hist, "dominance_history")):
            p = points(res[res.method == "conformal"], "pruner")
            b = base[base.design.isin(p["designs"])]
            for r in (p, points(b[b.method == "physics"], "physics"),
                      points(b[b.method == heur], "dominance"),
                      points(b[b.method == "oracle"], "oracle")):
                r.update(panel=panel, g_hold=g, n_designs=len(r.pop("designs")))
                rows.append(r)
    return pd.DataFrame(rows)


def draw(ax, title, pts, color, source):
    pf.style(ax, title, "Hold guard band g_hold, ps (g_setup = 0, α = 1%)")
    o = pts[pts.method == "oracle"]
    ax.plot(o.g_hold, o.saved, ":", color=pf.INK2, lw=1.2, zorder=2)
    pf.label(ax, o.g_hold.iloc[0], o.saved.iloc[0], "oracle", -8, 0, "right")
    names = {"pruner": "conformal pruner", "physics": "physics rule",
             "dominance": f"dominant scenes\n({source})"}
    for m, c in color.items():
        s = pts[pts.method == m]
        ax.plot(s.g_hold, s.saved, "-", color=c, lw=2, zorder=3)
        ax.scatter(s.g_hold, s.saved, s=64, zorder=4, linewidth=2,
                   color=[c if ok else pf.SURFACE for ok in s.safe], edgecolor=c)
        pf.label(ax, s.g_hold.iloc[-1], s.saved.iloc[-1], names[m], 9, 0)
    ax.set_xticks(sorted(pts.g_hold.unique()))
    ax.set_xlim(pts.g_hold.min() - 4, pts.g_hold.max() + 16)
    ax.set_ylim(-5, 100)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corners", default="corners_derate_pvt_rcx", help="results dir under work/")
    ap.add_argument("--anchors", nargs=2, default=["fast_cb", "slow_cw"], metavar="SCENE")
    ap.add_argument("--guards", nargs="+", type=float, default=list(range(10, 55, 5)), metavar="PS")
    ap.add_argument("--k", type=int, default=3, help="calibration runs for the with-history panel")
    ap.add_argument("--theme", choices=pf.THEMES, default="dark")
    args = ap.parse_args()
    pf.set_theme(args.theme)
    color = dict(zip(METHODS, pf.THEMES[args.theme]["series"]))
    d = cp.WORK / "prune" / args.corners
    pts = load(d, "-".join(args.anchors), args.guards, args.k)

    fig, axes = plt.subplots(1, 2, figsize=pf.SIZE, sharey=True, facecolor=pf.SURFACE)
    titles = {"new design": "New design (no history): linear model",
              "with history": f"With {args.k} past runs of the design: LightGBM"}
    for ax, (panel, title) in zip(axes, titles.items()):
        p = pts[pts.panel == panel]
        source = "other designs" if panel == "new design" else "past runs"
        draw(ax, f"{title}\n{p.n_designs.iloc[0]} designs", p, color, source)
    axes[0].set_ylabel("Compute saved, % of full 12-scene STA", fontsize=9 * pf.FONT, color=pf.INK2)
    handles = [Line2D([], [], color=c, lw=2, marker="o", ms=7, mec=c, mew=2) for c in color.values()]
    handles += [Line2D([], [], color=pf.INK2, lw=1.2, ls=":"),
                Line2D([], [], ls="", marker="o", ms=7, mfc=pf.SURFACE, mec=pf.INK2, mew=2)]
    labels = ["conformal pruner", "physics rule (anchors only)", "dominant scenes",
              "oracle: skip exactly the clean scenes", f"hollow: < {SAFE:.0%} of violations caught"]
    ncol = 5 if pf.FONT == 1 else 3
    fig.legend(handles, labels, loc="lower center", ncol=ncol, frameon=False,
               fontsize=8.5 * pf.FONT, labelcolor=pf.INK2)
    fig.tight_layout(rect=(0, 0.07 * 5 / ncol, 1, 1))

    out = cp.WORK / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "guard.png", dpi=300, facecolor=pf.SURFACE)
    fig.savefig(out / "guard.svg", facecolor=pf.SURFACE)
    pts.round(1).to_csv(out / "guard.csv", index=False)
    print(f"wrote {out / 'guard.png'}")
    pd.set_option("display.width", 200)
    print(pts.pivot_table(index=["panel", "method"], columns="g_hold",
                          values=["saved", "worst"]).round(1).to_string())


if __name__ == "__main__":
    main()
