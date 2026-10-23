"""Gate 1: is corner dominance non-trivial? (is there anything to prune?)

    .venv/bin/python scripts/gate1_dominance.py <design>_<variant> [--guard PS]

Reads work/corners/<design>_<variant>/<pvt>_<rc>_endpoints.csv from
scripts/corner_sta.sh. For each check, an endpoint violates at a scene if its
slack is below the guard band. Reports, for PVT only (nominal RC) and for
PVT x RC (scaled RC corners):

- violating endpoints and endpoint-scene pairs;
- how often each scene is an endpoint's worst;
- what the physics rule (one scene: slowest for setup, fastest for hold)
  catches, by endpoint and by pair (pair recall is the outline's metric);
- how many scenes a greedy cover needs to catch every violating endpoint.

Dominance is trivial if the physics rule catches every violating endpoint.
"""

import argparse
import os
from pathlib import Path

import pandas as pd

WORK = Path(os.environ.get("WORK_HOME", Path(__file__).resolve().parents[1] / "work"))

# Physics-rule scene per check: slowest corner for setup, fastest for hold.
PHYSICS = {
    "pvt": {"setup": "slow_nom", "hold": "fast_nom"},
    "pvt_rc": {"setup": "slow_rcw", "hold": "fast_rcb"},
}


def load(run):
    frames = []
    for path in sorted((WORK / "corners" / run).glob("*_endpoints.csv")):
        df = pd.read_csv(path)
        df["scene"] = path.name.removesuffix("_endpoints.csv")
        frames.append(df)
    if not frames:
        raise SystemExit(f"no endpoint CSVs in {WORK / 'corners' / run}")
    return pd.concat(frames, ignore_index=True)


def greedy_cover(viol):
    """Scenes picked greedily until every violating endpoint is caught."""
    remaining = set(viol.index[viol.any(axis=1)])
    picked = []
    while remaining:
        best = max(viol.columns, key=lambda s: viol.loc[list(remaining), s].sum())
        picked.append(best)
        remaining -= set(viol.index[viol[best]])
    return picked


def report(slack, rule, guard):
    viol = slack < guard
    viol_eps = viol.any(axis=1)
    n_eps, n_pairs = int(viol_eps.sum()), int(viol.values.sum())
    print(f"  violating endpoints {n_eps} / {len(slack)}, pairs {n_pairs}")
    if n_eps == 0:
        return
    worst = slack[viol_eps].idxmin(axis=1).value_counts()
    print("  worst scene (violating endpoints): "
          + ", ".join(f"{s} {n}" for s, n in worst.items()))
    caught_eps = int(viol.loc[viol_eps, rule].sum())
    print(f"  physics rule {rule}: endpoints {caught_eps}/{n_eps} "
          f"({caught_eps / n_eps:.1%}), pair recall "
          f"{viol[rule].sum() / n_pairs:.1%}")
    cover = greedy_cover(viol)
    print(f"  greedy cover of all violating endpoints: {len(cover)} scene(s) "
          f"{cover}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", help="<design>_<variant>")
    ap.add_argument("--guard", type=float, default=0.0,
                    help="guard band g in ps: slack < g violates (default 0)")
    args = ap.parse_args()

    df = load(args.run)
    print(f"{args.run}, guard band {args.guard} ps")
    for check in ("setup", "hold"):
        wide = df[df.check == check].pivot(index="endpoint", columns="scene",
                                           values="slack_ps")
        nom = [s for s in wide.columns if s.endswith("_nom")]
        rc = [s for s in wide.columns if not s.endswith("_nom")]
        for name, scenes in (("pvt", nom), ("pvt_rc", rc)):
            rule = PHYSICS[name][check]
            if rule not in scenes:
                continue
            print(f"{check} / {name} ({len(scenes)} scenes)")
            report(wide[scenes], rule, args.guard)


if __name__ == "__main__":
    main()
