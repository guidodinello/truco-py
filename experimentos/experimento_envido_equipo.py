"""
Experimento: P(equipo A gana envido | mejor envido del equipo A == Y)

Simula en un único pase y agrupa por Y, para ver el umbral a partir del cual
conviene tocar envido como pie (último jugador del equipo).

Supuesto: empate → pierde el pie (éxito solo si max_A > max_B estricto).
"""

import math
import random

from engine.truco import EQUIPO_A, EQUIPO_B, construir_mazo, simular_mano


def _simulate(n, seed):
    rng = random.Random(seed)
    mazo = construir_mazo()

    # buckets[y] = [total, wins]
    buckets = {}

    for _ in range(n):
        r = simular_mano(mazo, rng)
        max_A = max(r["envidos"][i] for i in EQUIPO_A)
        max_B = max(r["envidos"][i] for i in EQUIPO_B)
        if max_A not in buckets:
            buckets[max_A] = [0, 0]
        buckets[max_A][0] += 1
        if max_A > max_B:
            buckets[max_A][1] += 1

    return {"n": n, "seed": seed, "buckets": buckets}


def _report(r):
    n = r["n"]
    buckets = r["buckets"]
    z = 1.96

    print(f"\n{'=' * 65}")
    print(f"  P(ganar envido | mejor envido del equipo == Y)  —  n = {n:,}")
    print(f"  Supuesto: empate pierde el pie  |  semilla = {r['seed']}")
    print(f"{'=' * 65}")
    print(f"  {'Y':>4}  {'Manos':>8}  {'P(ganar)':>10}  {'IC 95%':^25}  {'SE':>8}")
    print(f"  {'-' * 61}")

    for y in sorted(buckets):
        total, wins = buckets[y]
        if total < 30:
            continue
        p = wins / total
        se = math.sqrt(p * (1 - p) / total)
        lo, hi = max(0.0, p - z * se), min(1.0, p + z * se)
        marker = " ← 50%" if abs(p - 0.5) < 0.02 else ""
        print(
            f"  {y:>4}  {total:>8,}  {p * 100:>9.1f}%"
            f"  [{lo * 100:.1f}% , {hi * 100:.1f}%]  {se * 100:>7.2f}%{marker}"
        )

    print(f"{'=' * 65}")


EXPERIMENTO = {
    "description": (
        "Simulación Monte Carlo — Envido en Truco Uruguayo\n"
        "P(ganar envido | mejor envido del equipo == Y), barrido completo"
    ),
    "simulate": _simulate,
    "report_fn": _report,
}
