"""
Experimento: P(al menos 2 jugadores del mismo equipo tienen flor)
"""

import random

from engine.truco import EQUIPO_A, EQUIPO_B, PALO_SIM, PALOS, construir_mazo, simular, simular_mano


def _report(r):
    n = r["n"]
    print(f"\n{'=' * 55}")
    print(f"  Simulación con n = {n:,}  |  semilla = {r['seed']}")
    print(f"{'=' * 55}")
    print(f"  Manos con éxito   : {r['exitos']:,}")
    print(f"  Probabilidad est. : {r['p'] * 100:.4f}%")
    print(f"  IC 95%            : [{r['ic_low'] * 100:.4f}% , {r['ic_high'] * 100:.4f}%]")
    print(f"  Error estándar    : {r['se'] * 100:.4f}%")

    print("\n  Desglose — jugadores con flor por mano (total):")
    print(f"  {'N° con flor':>12}  {'Frecuencia':>12}  {'%':>8}")
    print(f"  {'-' * 36}")
    for k in range(7):
        cnt = r["breakdown"].get(k, 0)
        print(f"  {k:>12}  {cnt:>12,}  {cnt / n * 100:>7.2f}%")

    print("\n  Desglose por equipo — (flores A, flores B) por mano:")
    print(f"  {'Flores A':>10}  {'Flores B':>10}  {'Frecuencia':>12}  {'%':>8}")
    print(f"  {'-' * 46}")
    for fa in range(4):
        for fb in range(4):
            cnt = r["breakdown_AB"].get((fa, fb), 0)
            if cnt == 0:
                continue
            marker = " *" if fa >= 2 or fb >= 2 else ""
            print(f"  {fa:>10}  {fb:>10}  {cnt:>12,}  {cnt / n * 100:>7.2f}%{marker}")
    print("  (* al menos un equipo con ≥2 flores)")


def _ejemplo(seed):
    rng = random.Random(seed)
    mazo = construir_mazo()
    r = simular_mano(mazo, rng)

    print(f"\n{'=' * 55}")
    print(f"  Mano de ejemplo (semilla {seed})")
    print(f"{'=' * 55}")
    palo_m, num_m = r["muestra"]
    print(f"  Muestra: {num_m} de {PALOS[palo_m]}  →  piezas en {PALOS[palo_m]}")
    print()
    for i, (mano, flor) in enumerate(zip(r["manos"], r["flores"], strict=False)):
        equipo = "A" if i % 2 == 0 else "B"
        cartas = "  ".join(f"{n}{PALO_SIM[p]}" for p, n in mano)
        estado = "★ FLOR" if flor else "  sin flor"
        print(f"  J{i + 1} (Equipo {equipo}): {cartas}   {estado}")

    flores_A = sum(r["flores"][i] for i in EQUIPO_A)
    flores_B = sum(r["flores"][i] for i in EQUIPO_B)
    print(f"\n  Equipo A: {flores_A} jugadores con flor")
    print(f"  Equipo B: {flores_B} jugadores con flor")
    print(f"  Resultado: {'ÉXITO (≥2 del mismo equipo)' if r['exito'] else 'sin éxito'}")


EXPERIMENTO = {
    "description": (
        "Simulación Monte Carlo — Flor en Truco Uruguayo\n"
        "P(al menos 2 jugadores del mismo equipo tienen flor)"
    ),
    "simulate": lambda n, seed: simular(n, seed=seed),
    "report_fn": _report,
    "ejemplo_fn": _ejemplo,
}
