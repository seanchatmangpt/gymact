#!/usr/bin/env python3
"""Deterministic timing benchmark for gymact.policy_ecology.

Measures the two hot paths of the policy-population layer on seeded synthetic
populations over the nine default temperament axes:

* ``population_diversity`` -- O(n^2) weighted pairwise disparity
* ``condition_population`` -- O(n * axes) adaptive reaction-norm conditioning
* ``policy_population_to_rdf`` / ``rdf_to_policy_population`` -- public-ontology
  projection and whole-graph-bound reconstruction (O(n * axes) triples)

Inputs are generated from a fixed seed, so the computed metrics (not the
timings) are byte-identical across runs; the JSON carries a result digest so
a replay can check that. Timings are the minimum over ``--repeat`` runs.

Usage: python scripts/bench_policy_ecology.py [--sizes 16,64,256] [--repeat 5] [--out FILE]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from pathlib import Path

from gymact.policy_ecology import (
    DEFAULT_TEMPERAMENT_AXES,
    PolicyPhenotype,
    PolicyPopulation,
    PopulationKind,
    ReactionNorm,
    StrategicCondition,
    WeightedPhenotype,
    condition_population,
    population_diversity,
)
from gymact.policy_ecology_rdf import policy_population_to_rdf, rdf_to_policy_population

SEED = 2609_29423


def build_population(size: int, seed: int = SEED) -> PolicyPopulation:
    rng = random.Random(seed + size)
    axes = [axis.axis_id for axis in DEFAULT_TEMPERAMENT_AXES]
    members = tuple(
        WeightedPhenotype(
            phenotype=PolicyPhenotype(
                policy_ref=f"policy:{index}",
                condition=StrategicCondition(
                    values=tuple((axis, round(rng.random(), 6)) for axis in axes)
                ),
            ),
            weight=round(rng.uniform(0.1, 10.0), 6),
        )
        for index in range(size)
    )
    return PolicyPopulation(
        kind=PopulationKind.ADAPTIVE,
        reaction_norm=ReactionNorm(
            slopes=tuple((axis, round(rng.uniform(-1.0, 1.0), 6)) for axis in axes)
        ),
        members=members,
    )


def _best_seconds(fn, repeat: int) -> float:
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def run(sizes: list[int], repeat: int) -> dict:
    rows = []
    digest = hashlib.sha256()
    for size in sizes:
        population = build_population(size)
        diversity = population_diversity(population)
        conditioned = condition_population(population, cue=0.5)
        digest.update(f"{size}:{diversity.model_dump_json()}".encode())
        digest.update(conditioned.model_dump_json().encode())
        pairs = size * (size - 1) // 2
        diversity_s = _best_seconds(lambda p=population: population_diversity(p), repeat)
        condition_s = _best_seconds(lambda p=population: condition_population(p, cue=0.5), repeat)
        graph = policy_population_to_rdf(population)
        if rdf_to_policy_population(graph) != population:
            raise SystemExit("REFUSED:BENCH_RDF_ROUND_TRIP_NOT_LOSSLESS")
        project_s = _best_seconds(lambda p=population: policy_population_to_rdf(p), repeat)
        reconstruct_s = _best_seconds(lambda g=graph: rdf_to_policy_population(g), repeat)
        rows.append(
            {
                "members": size,
                "pairs": pairs,
                "disparity": round(diversity.disparity, 12),
                "complexity": round(diversity.complexity, 12),
                "diversity_seconds": diversity_s,
                "diversity_ns_per_pair": (diversity_s * 1e9 / pairs) if pairs else None,
                "condition_seconds": condition_s,
                "condition_us_per_member": condition_s * 1e6 / size,
                "rdf_triples": len(graph),
                "rdf_project_us_per_member": project_s * 1e6 / size,
                "rdf_reconstruct_us_per_member": reconstruct_s * 1e6 / size,
            }
        )
    return {
        "benchmark": "gymact.policy_ecology",
        "seed": SEED,
        "repeat": repeat,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "result_digest": digest.hexdigest(),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="16,64,256")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    sizes = [int(part) for part in args.sizes.split(",") if part]
    if not sizes or min(sizes) < 1 or args.repeat < 1:
        print("REFUSED:BENCH_REQUIRES_POSITIVE_SIZES_AND_REPEAT", file=sys.stderr)
        return 2
    report = run(sizes, args.repeat)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
