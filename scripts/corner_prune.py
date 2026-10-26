"""Part A: conformal corner pruning, evaluated leave-one-design-out.

    .venv/bin/python scripts/corner_prune.py cross [--splits 5]
    .venv/bin/python scripts/corner_prune.py target [--k 1 2 3 5] [--splits 20]
        [--alpha-setup 0.01] [--alpha-hold 0.01] [--by-launch]
        [--designs aes,ibex,...] [--corners corners_derate] [--jobs 6]

Reads work/<corners>/<design>_<variant>/<pvt>_<rc>_endpoints.csv from
DERATE=1 scripts/corner_sta.sh. STA runs at the two anchor scenes; for every
endpoint, check and other scene, a LightGBM model predicts slack from the
anchors' slack, arrival and required time (F1). A pair violates if its true
slack is below the guard band g. Calibration sets, per check, the threshold
tau at the conformal quantile of predicted slack over violating calibration
pairs, so at least 1 - alpha of violating pairs get predicted slack <= tau
(pair recall). A scene runs if it is an anchor or any of its pairs is flagged
in either check.

Each design is held out in turn. Models are fit on the other designs.

- cross: the other designs' runs are split at random, by run, into halves;
  one half fits the models and the other calibrates. --splits draws.
- target: models are fit on all other designs' runs and calibrated on k runs
  of the held-out design; its remaining runs are tested. --splits draws per k.

--by-launch calibrates port-launched and register-launched pairs separately
(Mondrian conformal), so the bound holds within each class. The class is the
worst path's start_class at the anchor with the lower slack; self-loops count
as register-launched. A class with too few calibration violators for a finite
threshold (fewer than 1/alpha - 1) uses the pooled threshold of its check, so
the per-class bound holds only for classes that calibrate on their own.

Per-split results go to work/prune/<mode>[_launch].csv; the summary prints
mean ± std per held-out design.
"""

import argparse
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

WORK = Path(os.environ.get("WORK_HOME", Path(__file__).resolve().parents[1] / "work"))

SCENES = [f"{p}_{r}" for p in ("fast", "typical", "slow") for r in ("cw", "rcw", "cb", "rcb")]
ANCHORS = ("fast_cb", "slow_rcw")
TARGETS = [s for s in SCENES if s not in ANCHORS]
PRED = [f"p_{s}" for s in TARGETS]
CHECKS = ("setup", "hold")
GUARD = {"setup": 0.0, "hold": 40.0}
LAUNCH = ("port", "reg")
FEATURES = [f"{a}_{c}" for a in ANCHORS for c in ("slack_ps", "arrival_ps", "required_ps")]

# Near-critical pairs (true slack within NEAR ps above g) get extra weight.
NEAR, NEAR_WEIGHT = 50.0, 10.0
MODEL = dict(n_estimators=500, learning_rate=0.05, verbose=-1, n_jobs=2)


def load_run(path):
    d = {s: pd.read_csv(path / f"{s}_endpoints.csv").set_index(["endpoint", "check"])
         for s in SCENES}
    df = pd.concat([d[a][["slack_ps", "arrival_ps", "required_ps"]].add_prefix(f"{a}_")
                    for a in ANCHORS], axis=1)
    first = df[f"{ANCHORS[0]}_slack_ps"] <= df[f"{ANCHORS[1]}_slack_ps"]
    df["base"] = df[f"{ANCHORS[0]}_slack_ps"].where(first, df[f"{ANCHORS[1]}_slack_ps"])
    start = d[ANCHORS[0]].start_class.reindex(df.index).where(
        first, d[ANCHORS[1]].start_class.reindex(df.index))
    df["launch"] = start.replace("self", "reg")
    for s in TARGETS:
        df[s] = d[s].slack_ps
    return df.dropna().reset_index()


def load(corners, designs):
    frames = []
    for path in sorted((WORK / corners).iterdir()):
        design = path.name.rsplit("_p", 1)[0]
        if designs and design not in designs:
            continue
        df = load_run(path)
        df["run"], df["design"] = path.name, design
        frames.append(df)
    if not frames:
        raise SystemExit(f"no runs in {WORK / corners}")
    df = pd.concat(frames, ignore_index=True)
    df["g"] = df.check.map(GUARD)
    return df


def fit_predict(fit, *frames):
    """Fit one model per check and target scene; add p_<scene> predicted slack to frames."""
    out = [f.copy() for f in frames]
    for check in CHECKS:
        f = fit[fit.check == check]
        for s in TARGETS:
            w = np.where(f[s] < f.g + NEAR, NEAR_WEIGHT, 1.0)
            m = lgb.LGBMRegressor(**MODEL).fit(f[FEATURES], f[s] - f.base, sample_weight=w)
            for o in out:
                rows = o.check == check
                o.loc[rows, f"p_{s}"] = o.loc[rows, "base"] + m.predict(o.loc[rows, FEATURES])
    return out


def conformal_quantile(scores, alpha):
    n = len(scores)
    k = math.ceil((1 - alpha) * (n + 1))
    return np.inf if k > n else np.sort(scores)[k - 1]


def calibrate(cal, alpha, by_launch):
    """Threshold and violator count per (check, launch group); group None if pooled.

    A launch group with too few calibration violators for a finite quantile
    takes the pooled threshold instead of flagging every pair in the group.
    """
    tau, n_cal = {}, {}
    for check in CHECKS:
        c = cal[cal.check == check]
        for grp in ((None,) + LAUNCH if by_launch else (None,)):
            cg = c if grp is None else c[c.launch == grp]
            viol = cg[TARGETS].values < GUARD[check]
            scores = cg[PRED].values[viol]
            t = conformal_quantile(scores, alpha[check])
            tau[check, grp] = tau[check, None] if grp and np.isinf(t) else t
            n_cal[check, grp] = len(scores)
        if by_launch:
            del tau[check, None], n_cal[check, None]
    return tau, n_cal


def evaluate(test, tau, by_launch):
    grp = test.launch if by_launch else [None] * len(test)
    thr = np.array([tau[c, g] for c, g in zip(test.check, grp)])
    flag = test[PRED].values <= thr[:, None]
    viol = test[TARGETS].values < test.g.values[:, None]

    runs = test.run.values
    ran = pd.DataFrame(flag).groupby(runs).any()
    dirty = pd.DataFrame(viol).groupby(runs).any()
    in_ran = ran.loc[runs].values

    res = dict(skipped=(~ran).values.sum(axis=1).mean() / len(SCENES),
               ceiling=(~dirty).values.sum(axis=1).mean() / len(SCENES))
    for check in CHECKS:
        rows = (test.check == check).values
        v = viol[rows]
        n = v.sum()
        res[f"viol_{check}"] = (v & in_ran[rows]).sum() / n if n else np.nan
        res[f"pair_{check}"] = (v & flag[rows]).sum() / n if n else np.nan
        for g in LAUNCH:
            vg = v & (test.launch.values[rows] == g)[:, None]
            ng = vg.sum()
            res[f"pair_{check}_{g}"] = (vg & flag[rows]).sum() / ng if ng else np.nan
    return res


def summary_row(res, tau, n_cal):
    for (check, grp), t in tau.items():
        key = check if grp is None else f"{check}_{grp}"
        res[f"tau_{key}"], res[f"ncal_{key}"] = t, n_cal[check, grp]
    return res


DATA = None


def _init(corners, designs):
    global DATA
    DATA = load(corners, designs)


def run_cross(design, args):
    test, others = DATA[DATA.design == design], DATA[DATA.design != design]
    pool = np.sort(others.run.unique())
    rows = []
    for split in range(args.splits):
        rng = np.random.default_rng(split)
        cal_runs = rng.choice(pool, len(pool) // 2, replace=False)
        is_cal = others.run.isin(cal_runs)
        cal, tst = fit_predict(others[~is_cal], others[is_cal], test)
        tau, n_cal = calibrate(cal, args.alpha, args.by_launch)
        res = evaluate(tst, tau, args.by_launch)
        rows.append(summary_row(dict(design=design, split=split, **res), tau, n_cal))
    return rows


def run_target(design, args):
    target, others = DATA[DATA.design == design], DATA[DATA.design != design]
    (target,) = fit_predict(others, target)
    pool = np.sort(target.run.unique())
    rows = []
    for k in args.k:
        if k >= len(pool):
            continue
        for split in range(args.splits):
            rng = np.random.default_rng(split)
            cal_runs = rng.choice(pool, k, replace=False)
            is_cal = target.run.isin(cal_runs)
            tau, n_cal = calibrate(target[is_cal], args.alpha, args.by_launch)
            res = evaluate(target[~is_cal], tau, args.by_launch)
            rows.append(summary_row(dict(design=design, k=k, split=split, **res), tau, n_cal))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("cross", "target"))
    ap.add_argument("--alpha-setup", type=float, default=0.01)
    ap.add_argument("--alpha-hold", type=float, default=0.01)
    ap.add_argument("--by-launch", action="store_true",
                    help="calibrate port- and register-launched pairs separately")
    ap.add_argument("--splits", type=int, help="random draws (default 5 cross, 20 target)")
    ap.add_argument("--k", type=int, nargs="+", default=[1, 2, 3, 5],
                    help="target-design calibration runs (target mode)")
    ap.add_argument("--designs", help="comma-separated design pool (default: all)")
    ap.add_argument("--corners", default="corners_derate", help="results dir under work/")
    ap.add_argument("--jobs", type=int, default=6, help="held-out designs run at once")
    args = ap.parse_args()
    args.alpha = {"setup": args.alpha_setup, "hold": args.alpha_hold}
    args.splits = args.splits or (5 if args.mode == "cross" else 20)
    designs = args.designs.split(",") if args.designs else None

    held_out = designs or sorted({p.name.rsplit("_p", 1)[0]
                                  for p in (WORK / args.corners).iterdir()})
    work = run_cross if args.mode == "cross" else run_target
    with ProcessPoolExecutor(min(args.jobs, len(held_out)), initializer=_init,
                             initargs=(args.corners, designs)) as ex:
        rows = [r for rs in ex.map(work, held_out, [args] * len(held_out)) for r in rs]
    res = pd.DataFrame(rows)

    out = WORK / "prune" / f"{args.mode}{'_launch' if args.by_launch else ''}.csv"
    out.parent.mkdir(exist_ok=True)
    res.to_csv(out, index=False)

    keys = ["design"] + (["k"] if args.mode == "target" else [])
    cols = ["skipped", "ceiling", "viol_setup", "viol_hold", "pair_setup", "pair_hold",
            "pair_setup_port", "pair_hold_port"]
    g = res.groupby(keys)[cols]
    table = ((g.mean() * 100).round(1).astype(str) + " ± "
             + (g.std() * 100).round(1).astype(str))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(f"{args.mode}{' by launch' if args.by_launch else ''}, "
          f"alpha setup {args.alpha_setup} hold {args.alpha_hold}, {args.splits} splits")
    print(table)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
