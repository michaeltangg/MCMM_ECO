"""Part A figures: compute saved vs violations caught, pruner vs baselines.

    .venv/bin/python scripts/prune_figure.py [--corners corners_derate_pvt_rcx]
        [--anchors fast_cb slow_cw]

Reads the corner_prune.py sweeps (--alpha-setup/--alpha-hold/--margins, tag
_sweep) and prune_baselines.py from work/prune/<corners>/:

- new design: cross --cal-split design --model linear (calibration designs
  unseen by the model, like the held-out one);
- with history: target --k 5 (LightGBM, calibrated on 5 runs of the design).

Each point is the mean over held-out designs of per-design means; a panel
averages the baselines over the same designs as its pruner results. Recalls
are the mean of setup and hold. The conformal curve uses equal alpha for both
checks. Writes to work/figures/:

- tradeoff.png: compute saved vs violations caught (share of violating pairs
  in scenes that run), conformal pruner vs heuristics, oracle as a line;
- threshold.png: compute saved vs pair recall (share of violating pairs
  flagged), conformal vs the same predictions with a fixed margin over g for
  both checks. Conformal sets each check's threshold from calibration data and
  flags everything when a check has too few calibration violators for the
  bound, so the curves differ;
- tradeoff.csv: every plotted point.
"""

import argparse

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import corner_prune as cp  # noqa: E402

# Reference palette (dataviz skill), light mode; first three slots validate all-pairs.
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COLOR = {"conformal": "#2a78d6", "heuristic": "#eb6834", "margin": "#1baf7a"}
NAMES = {"physics": "physics rule", "dominance_cross": "dominant scenes\n(other designs)",
         "dominance_history": "dominant scenes\n(past runs)"}


def design_mean(df, keys):
    df = df.assign(caught=(df.viol_setup + df.viol_hold) / 2)
    df["pair"] = ((df.pair_setup + df.pair_hold) / 2) if "pair_setup" in df else df.caught
    per = df.groupby(keys + ["design"])[["saved", "caught", "pair"]].mean()
    return per.groupby(keys).mean().mul(100).reset_index(), per.reset_index().design.unique()


def panel_points(sweep, base, heuristics):
    conf = sweep[(sweep.method == "conformal") & (sweep.alpha_setup == sweep.alpha_hold)]
    conf, designs = design_mean(conf, ["alpha_setup"])
    margin, _ = design_mean(sweep[sweep.method == "margin"], ["margin"])
    base = base[base.design.isin(designs) & base.method.isin(heuristics + ["oracle"])]
    base, _ = design_mean(base, ["method"])
    return conf, margin, base, designs


def style(ax, title, xlabel):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel(xlabel, fontsize=9, color=INK2)


def label(ax, x, y, text, dx, dy, ha="left"):
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha,
                va="center", fontsize=8, color=INK2)


def draw_tradeoff(ax, title, conf, margin, base):
    style(ax, title, "Violations caught, % (mean of setup and hold)")
    o = base[base.method == "oracle"].iloc[0]
    ax.axhline(o.saved, color=INK2, lw=1, ls=":", zorder=2,
               label="oracle: skip exactly the clean scenes")
    label(ax, 2, o.saved, f"oracle {o.saved:.0f}%", 0, 7)
    ax.plot(conf.caught, conf.saved, "-o", color=COLOR["conformal"], lw=2, ms=8,
            mec=SURFACE, mew=2, label="conformal pruner, α = 1–20%", zorder=4)
    lo, hi = conf.iloc[0], conf.iloc[-1]
    label(ax, lo.caught, conf.saved.min(),
          f"α {lo.alpha_setup:.0%} → {hi.alpha_setup:.0%}: {lo.saved:.0f} → {hi.saved:.0f}% saved",
          0, -16, "right")
    heur = base[base.method != "oracle"]
    ax.scatter(heur.caught, heur.saved, s=70, color=COLOR["heuristic"], edgecolor=SURFACE,
               linewidth=2, label="heuristics", zorder=4)
    for _, r in heur.iterrows():
        label(ax, r.caught, r.saved, NAMES[r.method], 9, 0)
    ax.set_xlim(0, 104)
    ax.set_ylim(0, 100)


def draw_threshold(ax, title, conf, margin):
    style(ax, title, "Violating pairs flagged (pair recall), % (mean of setup and hold)")
    ax.plot(conf.pair, conf.saved, "-o", color=COLOR["conformal"], lw=2, ms=8,
            mec=SURFACE, mew=2, label="conformal threshold, α = 1–20%", zorder=4)
    for _, r in conf.iloc[[0, -1]].iterrows():
        ax.annotate(f"α {r.alpha_setup:.0%}", (r.pair, r.saved), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.plot(margin.pair, margin.saved, "-s", color=COLOR["margin"], lw=2, ms=7,
            mec=SURFACE, mew=2, label="fixed margin over g, 0–100 ps", zorder=3)
    for _, r in margin.iloc[[0, 1, -1]].iterrows():
        label(ax, r.pair, r.saved, f"{r.margin:g} ps", 9, 0)
    ax.set_ylim(-2, 32)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corners", default="corners_derate_pvt_rcx", help="results dir under work/")
    ap.add_argument("--anchors", nargs=2, default=["fast_cb", "slow_cw"], metavar="SCENE")
    args = ap.parse_args()
    d = cp.WORK / "prune" / args.corners
    a = "-".join(args.anchors)
    base = pd.read_csv(d / f"baselines_{a}.csv")
    panels = [
        ("New design (no history): linear model", pd.read_csv(d / f"cross_dsplit_{a}_sweep_linear.csv"),
         ["physics", "dominance_cross"]),
        ("With 5 past runs of the design: LightGBM", pd.read_csv(d / f"target_{a}_sweep.csv"),
         ["physics", "dominance_history"]),
    ]

    figs = {name: plt.subplots(1, 2, figsize=(11, 4.6), sharey=True, facecolor=SURFACE)
            for name in ("tradeoff", "threshold")}
    rows = []
    for i, (title, sweep, heuristics) in enumerate(panels):
        conf, margin, b, designs = panel_points(sweep, base, heuristics)
        title = f"{title}\n{len(designs)} designs"
        draw_tradeoff(figs["tradeoff"][1][i], title, conf, margin, b)
        draw_threshold(figs["threshold"][1][i], title, conf, margin)
        for kind, t, key in (("conformal", conf, "alpha_setup"), ("margin", margin, "margin"),
                             ("baseline", b, "method")):
            rows += [dict(panel=title.split("\n")[0], kind=kind, setting=r[key], saved=r.saved,
                          caught=r.caught, pair=r.pair) for _, r in t.iterrows()]

    out = cp.WORK / "figures"
    out.mkdir(parents=True, exist_ok=True)
    for name, (fig, axes) in figs.items():
        axes[0].set_ylabel("Compute saved, % of full 12-scene STA", fontsize=9, color=INK2)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8.5,
                   labelcolor=INK2)
        fig.tight_layout(rect=(0, 0.08, 1, 1))
        fig.savefig(out / f"{name}.png", dpi=200, facecolor=SURFACE)
        print(f"wrote {out / name}.png")
    pd.DataFrame(rows).round(1).to_csv(out / "tradeoff.csv", index=False)
    print(pd.DataFrame(rows).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
