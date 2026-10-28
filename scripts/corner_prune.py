"""Part A: conformal corner pruning, evaluated leave-one-design-out.

    .venv/bin/python scripts/corner_prune.py cross [--splits 5] [--cal-split run|design]
    .venv/bin/python scripts/corner_prune.py target [--k 1 2 3 5] [--splits 20]
        [--fit-runs 0 1 2] [--fit-weight 1]
        [--alpha-setup 0.01 ...] [--alpha-hold 0.01 ...] [--margins 0 10 ...] [--by-launch]
        [--model lgbm|linear] [--lgbm KEY=VALUE ...] [--near-weight 10] [--start-class]
        [--anchors fast_cb slow_rcw] [--guard-setup 0] [--guard-hold 40]
        [--designs aes,ibex,...] [--corners corners_derate] [--jobs 6]

Reads work/<corners>/<design>_<variant>/<pvt>_<rc>_endpoints.csv from
DERATE=1 scripts/corner_sta.sh. STA runs at the two anchor scenes; for every
endpoint, check and other scene, a model predicts slack from the anchors'
slack, arrival and required time (F1): LightGBM, or with --model linear the
Kahng-style linear regression baseline, both predicting the change from the
lower anchor slack. Fit rows whose true slack is within 50 ps above g (or
below it) get --near-weight (default 10). --lgbm overrides LightGBM
parameters (for example num_leaves=63 n_estimators=1000). --start-class adds whether the worst path launches from a
port or the endpoint's own instance at each anchor. --anchors picks the anchor
scenes (default fast_cb slow_rcw; one anchor for the ablation). A pair
violates if its true slack is below the guard band g (--guard-setup,
--guard-hold; default 0 and 40 ps). Calibration sets, per check, the threshold
tau at the conformal quantile of predicted slack over violating calibration
pairs, so at least 1 - alpha of violating pairs get predicted slack <= tau
(pair recall). A scene runs if it is an anchor or any of its pairs is flagged
in either check.

--alpha-setup and --alpha-hold take several values; every combination is
calibrated and evaluated from the same model fit (the model does not depend
on alpha). --margins adds the point-predictor baseline: the same predictions
with a fixed threshold g + margin (ps) instead of the conformal one. Rows carry
method (conformal or margin) and alpha_setup, alpha_hold or margin.

Compute: each scene costs its measured STA runtime (load, SPEF, update_timing
and both checks, from the scene JSON). saved is 1 - (anchors + scenes run +
model inference) / (all 12 scenes), per test run; saved_ceiling is the same
for running exactly the anchors and the scenes with violations. fit_s (model
fit and prediction) and cal_s (calibration) are one-time costs per split, not
per run.

--pairs also writes, for the first alpha combination, <tag>_misses.csv (every
violating pair not flagged: true and predicted slack, threshold, launch class,
whether its scene ran) and <tag>_pairstats.csv (counts of violating, missed
and wasted pairs, wasted meaning flagged in a scene with no violations, by
check, launch class, scene and slack - g bin), per split.

Each design is held out in turn. Models are fit on the other designs.

- cross: the other designs' runs are split at random, by run, into halves;
  one half fits the models and the other calibrates. --splits draws. With
  --cal-split design, whole designs are split instead (3 of the 7 calibrate,
  4 fit), so calibration designs are unseen by the models, like the held-out
  design; each split is a distinct design subset.
- target: k full runs of the held-out design are drawn; its remaining runs
  are tested. Models are fit on all other designs' runs and the k runs
  calibrate. --splits draws per k. With --fit-runs f > 0, f of the k runs
  join the fit set instead (their rows weighted by --fit-weight) and the
  other k - f calibrate, so calibration and test runs are both unseen by the
  models. At equal k and split, every f draws the same k runs.

--by-launch calibrates port-launched and register-launched pairs separately
(Mondrian conformal), so the bound holds within each class. The class is the
worst path's start_class at the anchor with the lower slack; self-loops count
as register-launched. A class with too few calibration violators for a finite
threshold (fewer than 1/alpha - 1) uses the pooled threshold of its check, so
the per-class bound holds only for classes that calibrate on their own.

Per-split results go to
work/prune/<mode>[_dsplit][_fit][_w<weight>][_launch][_start][_<a1>-<a2>][_<key><value>...][_nw<weight>][_g<setup>-<hold>][_sweep][_linear].csv
(anchors and guard bands tagged only if not the default; one _<key><value> per --lgbm override;
_nw if --near-weight is not 10;
_sweep if several alphas or any margins), under
work/prune/<corners>/ for any --corners other than corners_derate; the summary prints
mean ± std per held-out design.
"""

import argparse
import itertools
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

WORK = Path(os.environ.get("WORK_HOME", Path(__file__).resolve().parents[1] / "work"))

SCENES = [f"{p}_{r}" for p in ("fast", "typical", "slow") for r in ("cw", "rcw", "cb", "rcb")]
ANCHORS = ("fast_cb", "slow_rcw")
TARGETS = [s for s in SCENES if s not in ANCHORS]
PRED = [f"p_{s}" for s in TARGETS]
CHECKS = ("setup", "hold")
GUARD = {"setup": 0.0, "hold": 40.0}
LAUNCH = ("port", "reg")
FEATURES = [f"{a}_{c}" for a in ANCHORS for c in ("slack_ps", "arrival_ps", "required_ps")]
START_FEATURES = [f"{a}_{c}" for a in ANCHORS for c in ("port", "self")]

# Near-critical pairs (true slack within NEAR ps above g) get extra weight.
NEAR, NEAR_WEIGHT = 50.0, 10.0
MODEL = dict(n_estimators=500, learning_rate=0.05, verbose=-1, n_jobs=2)


def load_run(path):
    d = {s: pd.read_csv(path / f"{s}_endpoints.csv").set_index(["endpoint", "check"])
         for s in SCENES}
    df = pd.concat([d[a][["slack_ps", "arrival_ps", "required_ps"]].add_prefix(f"{a}_")
                    for a in ANCHORS], axis=1)
    slack = df[[f"{a}_slack_ps" for a in ANCHORS]].values
    low = np.argmin(np.nan_to_num(slack, nan=np.inf), axis=1)   # first anchor wins ties
    rows = np.arange(len(df))
    df["base"] = slack[rows, low]
    start = np.column_stack([d[a].start_class.reindex(df.index).values for a in ANCHORS])
    df["launch"] = pd.Series(start[rows, low], index=df.index).replace("self", "reg")
    for a in ANCHORS:
        cls = d[a].start_class.reindex(df.index)
        df[f"{a}_port"] = (cls == "port").astype(float)
        df[f"{a}_self"] = (cls == "self").astype(float)
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
    df["w"] = 1.0
    return df


def load_runtime(corners):
    """STA seconds per scene (rows: run, columns: scene) from the scene JSONs."""
    rt = {}
    for path in sorted((WORK / corners).iterdir()):
        rt[path.name] = {}
        for s in SCENES:
            j = json.loads((path / f"{s}.json").read_text())
            rt[path.name][s] = sum(j[k] for k in ("load_s", "spef_s", "update_s", "setup_s", "hold_s"))
    return pd.DataFrame.from_dict(rt, orient="index")[SCENES]


def fit_predict(fit, *frames, model="lgbm", features=FEATURES, params=None,
                near_weight=NEAR_WEIGHT):
    """Fit one model per check and target scene; add p_<scene> predicted slack to frames.

    infer_s spreads each predict call's wall time evenly over its rows, so a
    run's inference time is the sum over its rows.
    """
    out = [f.assign(infer_s=0.0) for f in frames]
    for check in CHECKS:
        f = fit[fit.check == check]
        for s in TARGETS:
            w = np.where(f[s] < f.g + NEAR, near_weight, 1.0) * f.w
            m = lgb.LGBMRegressor(**{**MODEL, **(params or {})}) if model == "lgbm" else LinearRegression()
            m.fit(f[features], f[s] - f.base, sample_weight=w)
            for o in out:
                rows = o.check == check
                t0 = time.perf_counter()
                o.loc[rows, f"p_{s}"] = o.loc[rows, "base"] + m.predict(o.loc[rows, features])
                o.loc[rows, "infer_s"] += (time.perf_counter() - t0) / max(rows.sum(), 1)
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


GAP_BINS = [-np.inf, -50, -20, -10, -5, 0, 5, 10, 20, 50, np.inf]


def pair_dump(test, flag, viol, thr, in_ran, dirty_scene):
    """Missed pairs, and counts of violating, missed and wasted pairs by class."""
    slack = test[TARGETS].values
    i, j = np.nonzero(viol & ~flag)
    misses = pd.DataFrame(dict(run=test.run.values[i], endpoint=test.endpoint.values[i],
                               check=test.check.values[i], launch=test.launch.values[i],
                               scene=np.array(TARGETS)[j], slack=slack[i, j],
                               pred=test[PRED].values[i, j], tau=thr[i], base=test.base.values[i],
                               ran=in_ran[i, j]))
    gap_bin = np.digitize(slack - test.g.values[:, None], GAP_BINS[1:-1])
    frames = []
    for kind, mask in (("viol", viol), ("miss", viol & ~flag), ("wasted", flag & ~dirty_scene)):
        i, j = np.nonzero(mask)
        frames.append(pd.DataFrame(dict(kind=kind, check=test.check.values[i],
                                        launch=test.launch.values[i], scene=np.array(TARGETS)[j],
                                        gap_bin=gap_bin[i, j]))
                      .value_counts().rename("n").reset_index())
    stats = pd.concat(frames, ignore_index=True)
    labels = [f"[{lo:g},{hi:g})" for lo, hi in zip(GAP_BINS[:-1], GAP_BINS[1:])]
    stats["gap_bin"] = stats.gap_bin.map(dict(enumerate(labels)))
    return misses, stats


def evaluate(test, tau, by_launch, pairs=False):
    grp = test.launch if by_launch else [None] * len(test)
    thr = np.array([tau[c, g] for c, g in zip(test.check, grp)])
    flag = test[PRED].values <= thr[:, None]
    viol = test[TARGETS].values < test.g.values[:, None]

    runs = test.run.values
    ran = pd.DataFrame(flag).groupby(runs).any()
    dirty = pd.DataFrame(viol).groupby(runs).any()
    in_ran = ran.loc[runs].values

    rt = RUNTIME.loc[ran.index]
    total = rt.sum(axis=1).values
    anchors = rt[list(ANCHORS)].sum(axis=1).values
    infer = test.groupby("run").infer_s.sum().loc[ran.index].values
    used = anchors + (ran.values * rt[TARGETS].values).sum(axis=1) + infer
    oracle = anchors + (dirty.values * rt[TARGETS].values).sum(axis=1)
    res = dict(skipped=(~ran).values.sum(axis=1).mean() / len(SCENES),
               ceiling=(~dirty).values.sum(axis=1).mean() / len(SCENES),
               saved=(1 - used / total).mean(), saved_ceiling=(1 - oracle / total).mean(),
               infer_s=infer.mean())
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
    if pairs:
        return res, pair_dump(test, flag, viol, thr, in_ran, dirty.loc[runs].values)
    return res


def summary_row(res, tau, n_cal):
    for (check, grp), t in tau.items():
        key = check if grp is None else f"{check}_{grp}"
        res[f"tau_{key}"], res[f"ncal_{key}"] = t, n_cal[check, grp]
    return res


def score(cal, test, args):
    """One result per alpha combination (conformal) and per fixed margin, plus the
    --pairs dump (misses, stats) of the first alpha combination, or None."""
    rows, dump = [], None
    for a_setup, a_hold in itertools.product(args.alpha_setup, args.alpha_hold):
        t0 = time.perf_counter()
        tau, n_cal = calibrate(cal, {"setup": a_setup, "hold": a_hold}, args.by_launch)
        cal_s = time.perf_counter() - t0
        ev = evaluate(test, tau, args.by_launch, pairs=args.pairs and dump is None)
        if isinstance(ev, tuple):
            ev, dump = ev
        res = dict(method="conformal", alpha_setup=a_setup, alpha_hold=a_hold, cal_s=cal_s, **ev)
        rows.append(summary_row(res, tau, n_cal))
    for m in args.margins:
        tau = {(c, g): GUARD[c] + m for c in CHECKS for g in (LAUNCH if args.by_launch else (None,))}
        res = dict(method="margin", margin=m, **evaluate(test, tau, args.by_launch))
        rows.append(summary_row(res, tau, dict.fromkeys(tau, np.nan)))
    return rows, dump


DATA = RUNTIME = None


def set_anchors(anchors):
    """Rebind the anchor-dependent module constants (each worker process too)."""
    global ANCHORS, TARGETS, PRED, FEATURES, START_FEATURES
    ANCHORS = tuple(anchors)
    TARGETS = [s for s in SCENES if s not in ANCHORS]
    PRED = [f"p_{s}" for s in TARGETS]
    FEATURES = [f"{a}_{c}" for a in ANCHORS for c in ("slack_ps", "arrival_ps", "required_ps")]
    START_FEATURES = [f"{a}_{c}" for a in ANCHORS for c in ("port", "self")]


def _init(corners, designs, anchors, guard):
    global DATA, RUNTIME
    set_anchors(anchors)
    GUARD.update(guard)
    DATA = load(corners, designs)
    RUNTIME = load_runtime(corners)


def run_cross(design, args):
    test, others = DATA[DATA.design == design], DATA[DATA.design != design]
    unit = args.cal_split
    pool = np.sort(others[unit].unique())
    if unit == "design":
        subsets = list(itertools.combinations(pool, len(pool) // 2))
        order = np.random.default_rng(0).permutation(len(subsets))
    rows, dumps = [], []
    for split in range(args.splits):
        if unit == "design":
            cal_units = list(subsets[order[split % len(subsets)]])
        else:
            cal_units = np.random.default_rng(split).choice(pool, len(pool) // 2, replace=False)
        is_cal = others[unit].isin(cal_units)
        t0 = time.perf_counter()
        cal, tst = fit_predict(others[~is_cal], others[is_cal], test, model=args.model,
                               features=args.features, params=args.lgbm,
                               near_weight=args.near_weight)
        fit_s = time.perf_counter() - t0
        results, dump = score(cal, tst, args)
        for res in results:
            row = dict(design=design, split=split, fit_s=fit_s, **res)
            if unit == "design":
                row["cal_designs"] = " ".join(cal_units)
            rows.append(row)
        if dump:
            dumps.append([d.assign(design=design, split=split) for d in dump])
    return rows, dumps


def run_target(design, args):
    target, others = DATA[DATA.design == design], DATA[DATA.design != design]
    pool = np.sort(target.run.unique())
    if 0 in args.fit_runs:
        t0 = time.perf_counter()
        (base,) = fit_predict(others, target, model=args.model, features=args.features,
                              params=args.lgbm, near_weight=args.near_weight)
        base_fit_s = time.perf_counter() - t0
    rows, dumps = [], []
    for k, f in itertools.product(args.k, args.fit_runs):
        if k >= len(pool) or f >= k:
            continue
        for split in range(args.splits):
            rng = np.random.default_rng(split)
            drawn = rng.choice(pool, k, replace=False)
            fit_runs, cal_runs = drawn[:f], drawn[f:]
            if f:
                is_fit = target.run.isin(fit_runs)
                hist = target[is_fit].assign(w=args.fit_weight)
                t0 = time.perf_counter()
                (pred,) = fit_predict(pd.concat([others, hist]), target[~is_fit],
                                      model=args.model, features=args.features,
                                      params=args.lgbm, near_weight=args.near_weight)
                fit_s = time.perf_counter() - t0
            else:
                pred, fit_s = base, base_fit_s
            is_cal = pred.run.isin(cal_runs)
            results, dump = score(pred[is_cal], pred[~is_cal], args)
            rows += [dict(design=design, k=k, fit=f, split=split, fit_s=fit_s, **res)
                     for res in results]
            if dump:
                dumps.append([d.assign(design=design, k=k, fit=f, split=split) for d in dump])
    return rows, dumps


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("cross", "target"))
    ap.add_argument("--alpha-setup", type=float, nargs="+", default=[0.01])
    ap.add_argument("--alpha-hold", type=float, nargs="+", default=[0.01])
    ap.add_argument("--margins", type=float, nargs="+", default=[],
                    help="fixed-margin baseline: flag predicted slack <= g + margin (ps)")
    ap.add_argument("--by-launch", action="store_true",
                    help="calibrate port- and register-launched pairs separately")
    ap.add_argument("--cal-split", choices=("run", "design"), default="run",
                    help="cross mode: split other designs' data into fit/cal by run or by design")
    ap.add_argument("--model", choices=("lgbm", "linear"), default="lgbm")
    ap.add_argument("--lgbm", nargs="+", default=[], metavar="KEY=VALUE",
                    help="LightGBM parameter overrides, e.g. num_leaves=63")
    ap.add_argument("--near-weight", type=float, default=NEAR_WEIGHT,
                    help=f"fit weight on pairs within {NEAR:g} ps above g (default {NEAR_WEIGHT:g})")
    ap.add_argument("--start-class", action="store_true",
                    help="add each anchor's worst-path start class as features")
    ap.add_argument("--anchors", nargs="+", choices=SCENES, default=list(ANCHORS),
                    metavar="SCENE", help="one or two anchor scenes (default fast_cb slow_rcw)")
    ap.add_argument("--guard-setup", type=float, default=GUARD["setup"], help="g for setup (ps)")
    ap.add_argument("--guard-hold", type=float, default=GUARD["hold"], help="g for hold (ps)")
    ap.add_argument("--splits", type=int, help="random draws (default 5 cross, 20 target)")
    ap.add_argument("--k", type=int, nargs="+", default=[1, 2, 3, 5],
                    help="target-design full runs (target mode)")
    ap.add_argument("--fit-runs", type=int, nargs="+", default=[0],
                    help="of the k target-design runs, how many join the fit set (target mode)")
    ap.add_argument("--fit-weight", type=float, default=1.0,
                    help="sample weight on target-design fit rows")
    ap.add_argument("--pairs", action="store_true",
                    help="also write missed pairs and violating/missed/wasted pair counts")
    ap.add_argument("--designs", help="comma-separated design pool (default: all)")
    ap.add_argument("--corners", default="corners_derate", help="results dir under work/")
    ap.add_argument("--jobs", type=int, default=6, help="held-out designs run at once")
    args = ap.parse_args()
    if len(args.anchors) > 2 or len(set(args.anchors)) < len(args.anchors):
        ap.error("--anchors takes one or two different scenes")
    default_anchors = args.anchors == list(ANCHORS)
    guard = {"setup": args.guard_setup, "hold": args.guard_hold}
    default_guard = guard == GUARD
    GUARD.update(guard)
    try:
        args.lgbm = {k: (float(v) if "." in v or "e" in v else int(v))
                     for k, v in (kv.split("=", 1) for kv in args.lgbm)}
    except ValueError:
        ap.error("--lgbm takes numeric KEY=VALUE pairs")
    if args.lgbm and args.model != "lgbm":
        ap.error("--lgbm needs --model lgbm")
    set_anchors(args.anchors)
    args.splits = args.splits or (5 if args.mode == "cross" else 20)
    args.features = FEATURES + (START_FEATURES if args.start_class else [])
    designs = args.designs.split(",") if args.designs else None

    held_out = designs or sorted({p.name.rsplit("_p", 1)[0]
                                  for p in (WORK / args.corners).iterdir()})
    work = run_cross if args.mode == "cross" else run_target
    with ProcessPoolExecutor(min(args.jobs, len(held_out)), initializer=_init,
                             initargs=(args.corners, designs, args.anchors, guard)) as ex:
        results = list(ex.map(work, held_out, [args] * len(held_out)))
    res = pd.DataFrame([r for rows, _ in results for r in rows])
    dumps = [d for _, ds in results for d in ds]

    fit = args.mode == "target" and max(args.fit_runs) > 0
    tag = (args.mode + ("_dsplit" if args.mode == "cross" and args.cal_split == "design" else "")
           + ("_fit" if fit else "")
           + (f"_w{args.fit_weight:g}" if fit and args.fit_weight != 1 else "")
           + ("_launch" if args.by_launch else "")
           + ("_start" if args.start_class else "")
           + ("" if default_anchors else "_" + "-".join(args.anchors))
           + "".join(f"_{k}{v:g}" for k, v in args.lgbm.items())
           + (f"_nw{args.near_weight:g}" if args.near_weight != NEAR_WEIGHT else "")
           + ("" if default_guard else f"_g{args.guard_setup:g}-{args.guard_hold:g}")
           + ("_sweep" if len(args.alpha_setup) > 1 or len(args.alpha_hold) > 1 or args.margins else "")
           + ("_linear" if args.model == "linear" else ""))
    out = WORK / "prune" / f"{tag}.csv"
    if args.corners != "corners_derate":
        out = WORK / "prune" / args.corners / f"{tag}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)
    if dumps:
        for i, name in enumerate(("misses", "pairstats")):
            path = out.with_name(f"{out.stem}_{name}.csv")
            pd.concat([d[i] for d in dumps], ignore_index=True).to_csv(path, index=False)
            print(f"wrote {path}")

    keys = ["design"] + (["k", "fit"] if args.mode == "target" else [])
    keys += [c for c in ("method", "alpha_setup", "alpha_hold", "margin")
             if c in res and res[c].nunique(dropna=False) > 1]
    cols = ["skipped", "ceiling", "saved", "viol_setup", "viol_hold", "pair_setup", "pair_hold",
            "pair_setup_port", "pair_hold_port"]
    g = res.groupby(keys, dropna=False)[cols]
    table = ((g.mean() * 100).round(1).astype(str) + " ± "
             + (g.std().fillna(0) * 100).round(1).astype(str))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(f"{tag}, alpha setup {args.alpha_setup} hold {args.alpha_hold}, "
          f"margins {args.margins}, {args.splits} splits")
    print(table)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
