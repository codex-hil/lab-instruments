#!/usr/bin/env python3
"""Synthetic PPS time error in seconds, sampled at 1 Hz. No hardware data."""
import random, math
from pathlib import Path
rng = random.Random(20261031)
out = Path(__file__).resolve().parents[1] / "evidence" / "synthetic-pps-seconds.txt"
out.parent.mkdir(parents=True, exist_ok=True)
walk = 0.0
with out.open("w") as f:
    for i in range(32768):
        walk += rng.gauss(0.0, 2e-12)
        x = 2e-10 * math.sin(2*math.pi*i/1000) + rng.gauss(0.0, 1e-10) + walk
        f.write(f"{x:.17e}\n")
print(out)
