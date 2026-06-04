"""
Experimento: P(ganar flor | tengo flor con X puntos, 1v2)

Escenario: jugador 0 tiene flor (equipo A) contra exactamente 2 jugadores
del equipo B con flor.  ¿A partir de qué puntaje conviene subir la apuesta?

Umbrales de EV:
  - EV(pasivo) > 0   cuando P > 2/3
  - EV(subir)  > EV(pasivo)  cuando P > 1/2  (para cualquier suba R > 0)
"""

import math
import random

from engine.truco import EQUIPO_A, EQUIPO_B, construir_mazo, simular_mano


def _simulate(n, seed):
    rng = random.Random(seed)
    mazo = construir_mazo()

    # buckets[pts] = [total, wins]
    buckets = {}
    n_filtradas = 0

    for _ in range(n):
        r = simular_mano(mazo, rng)
        flores = r["flores"]

        # Filtro: jugador 0 tiene flor, ningún compañero tiene flor, exactamente 2 rivales
        if not flores[0]:
            continue
        if sum(flores[i] for i in EQUIPO_A) != 1:
            continue
        if sum(flores[i] for i in EQUIPO_B) != 2:
            continue

        n_filtradas += 1

        my_pts = r["flores_pts"][0]
        opp_pts = max(r["flores_pts"][i] for i in EQUIPO_B if flores[i])
        won = my_pts > opp_pts

        if my_pts not in buckets:
            buckets[my_pts] = [0, 0]
        buckets[my_pts][0] += 1
        if won:
            buckets[my_pts][1] += 1

    return {"n": n, "n_filtradas": n_filtradas, "seed": seed, "buckets": buckets}


def _report(r):
    n = r["n"]
    n_filtradas = r["n_filtradas"]
    buckets = r["buckets"]
    z = 1.96

    print(f"\n{'=' * 70}")
    print("  P(ganar flor | mis pts de flor == X)  —  escenario 1v2")
    print(f"  n total = {n:,}   |   manos filtradas = {n_filtradas:,}   |   semilla = {r['seed']}")
    print(f"{'=' * 70}")
    print(f"  {'X':>4}  {'Manos':>8}  {'P(ganar)':>10}  {'IC 95%':^25}  {'SE':>8}")
    print(f"  {'-' * 66}")

    for x in sorted(buckets):
        total, wins = buckets[x]
        if total < 10:
            continue
        p = wins / total
        se = math.sqrt(p * (1 - p) / total)
        lo, hi = max(0.0, p - z * se), min(1.0, p + z * se)

        marker = ""
        if abs(p - 2 / 3) < 0.03:
            marker = " ← ~2/3"
        elif abs(p - 0.5) < 0.03:
            marker = " ← ~1/2"

        print(
            f"  {x:>4}  {total:>8,}  {p * 100:>9.1f}%"
            f"  [{lo * 100:.1f}% , {hi * 100:.1f}%]  {se * 100:>7.2f}%{marker}"
        )

    print(f"{'=' * 70}")


EXPERIMENTO = {
    "description": (
        "Simulación Monte Carlo — Decisión de Flor en Truco Uruguayo\n"
        "P(ganar flor | mis pts == X), escenario 1v2"
    ),
    "simulate": _simulate,
    "report_fn": _report,
}
