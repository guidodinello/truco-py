"""
Experimento: P(yo gano envido | mi envido == Y)

Escenario 1v1: mi puntaje contra el de un único oponente.
Supuesto: empate → pierdo (éxito solo si envido[0] > envido[1] estricto).

A diferencia de experimento_envido_equipo.py, aquí no hay agregación de equipo:
se compara directamente mi carta contra la de un solo rival.
"""

import math
import random

from engine.truco import construir_mazo, simular_mano


def _simulate(n, seed):
    rng = random.Random(seed)
    mazo = construir_mazo()

    buckets = {}

    for _ in range(n):
        r = simular_mano(mazo, rng)
        my_pts = r["envidos"][0]
        opp_pts = r["envidos"][1]

        if my_pts not in buckets:
            buckets[my_pts] = [0, 0]
        buckets[my_pts][0] += 1
        if my_pts > opp_pts:
            buckets[my_pts][1] += 1

    return {"n": n, "seed": seed, "buckets": buckets}


def _report(r):
    n = r["n"]
    buckets = r["buckets"]
    z = 1.96

    print(f"\n{'=' * 65}")
    print("  P(ganar envido | mi envido == Y)  —  escenario 1v1")
    print(f"  Supuesto: empate pierde  |  n = {n:,}  |  semilla = {r['seed']}")
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
        "P(ganar envido | mi envido == Y), escenario 1v1"
    ),
    "simulate": _simulate,
    "report_fn": _report,
}
