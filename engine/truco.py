"""
Simulación Monte Carlo — Truco Uruguayo
Probabilidad de que al menos dos jugadores del mismo equipo tengan flor.

Reglas implementadas:
  - Mazo español de 40 cartas (sin 8, 9).
  - 6 jugadores, 2 equipos de 3 (J1,J3,J5 = equipo A; J2,J4,J6 = equipo B).
  - La muestra (última carta del mazo barajado) define el palo de las piezas.
  - Tiene flor si cumple alguna de:
      a) 3 cartas del mismo palo (flor derecha).
      b) 1 pieza (2,4,5,10,11 del palo de la muestra) + las otras 2 del mismo palo.
      c) 2 o más piezas.
"""

import math
import random
from collections import Counter

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PALOS = ["Espadas", "Bastos", "Copas", "Oros"]
PALO_SIM = ["E", "B", "C", "O"]
NUMEROS = [1, 2, 3, 4, 5, 6, 7, 10, 11, 12]  # sin 8 ni 9
PIEZAS_NUMS = {2, 4, 5, 11, 10}

EQUIPO_A = [0, 2, 4]  # índices de jugadores (0-based)
EQUIPO_B = [1, 3, 5]


# ---------------------------------------------------------------------------
# Mazo y lógica de flor
# ---------------------------------------------------------------------------


def construir_mazo() -> list[tuple[int, int]]:
    """Retorna lista de 40 cartas como tuplas (palo_idx, numero)."""
    return [(p, n) for p in range(4) for n in NUMEROS]


def es_pieza(palo: int, numero: int, palo_muestra: int, numero_muestra: int) -> bool:
    """El 12 del palo de la muestra actúa como la muestra misma."""
    if palo != palo_muestra:
        return False
    n_efectivo = numero_muestra if numero == 12 else numero
    return n_efectivo in PIEZAS_NUMS


# ---------------------------------------------------------------------------
# Envido
# ---------------------------------------------------------------------------

PIEZA_ENVIDO_VAL = {2: 30, 4: 29, 5: 28, 11: 27, 10: 27}


def valor_envido_carta(palo: int, numero: int, palo_muestra: int, numero_muestra: int) -> int:
    if es_pieza(palo, numero, palo_muestra, numero_muestra):
        n_ef = numero_muestra if numero == 12 else numero
        return PIEZA_ENVIDO_VAL[n_ef]
    return numero if numero <= 7 else 0  # negras (10, 11, 12) = 0


def calcular_envido(mano: list[tuple[int, int]], palo_muestra: int, numero_muestra: int) -> int:
    vals = [(p, n, valor_envido_carta(p, n, palo_muestra, numero_muestra)) for p, n in mano]
    pieza_cards = [(p, n, v) for p, n, v in vals if es_pieza(p, n, palo_muestra, numero_muestra)]

    if pieza_cards:
        pieza_val = pieza_cards[0][2]
        other_vals = [v for p, n, v in vals if not es_pieza(p, n, palo_muestra, numero_muestra)]
        return pieza_val + max(other_vals, default=0)

    conteo = Counter(p for p, n in mano)
    max_palo, max_count = max(conteo.items(), key=lambda x: x[1])
    if max_count >= 2:
        same = sorted([v for p, n, v in vals if p == max_palo], reverse=True)[:2]
        return sum(same) + 20
    return max(v for p, n, v in vals)


# ---------------------------------------------------------------------------
# Flor
# ---------------------------------------------------------------------------


def calcular_flor(mano: list[tuple[int, int]], palo_muestra: int, numero_muestra: int) -> int:
    vals = [(p, n, valor_envido_carta(p, n, palo_muestra, numero_muestra)) for p, n in mano]
    pieza_cards = sorted(
        [(p, n, v) for p, n, v in vals if es_pieza(p, n, palo_muestra, numero_muestra)],
        key=lambda x: x[2],
        reverse=True,
    )
    non_pieza = [(p, n, v) for p, n, v in vals if not es_pieza(p, n, palo_muestra, numero_muestra)]
    n_p = len(pieza_cards)

    if n_p == 3:
        return pieza_cards[0][2] + (pieza_cards[1][2] % 10) + (pieza_cards[2][2] % 10)
    if n_p == 2:
        return pieza_cards[0][2] + (pieza_cards[1][2] % 10) + non_pieza[0][2]
    if n_p == 1:
        return pieza_cards[0][2] + sum(v for _, _, v in non_pieza)
    # flor derecha: 3 del mismo palo
    return sum(v for _, _, v in vals) + 20


def tiene_flor(mano: list[tuple[int, int]], palo_muestra: int, numero_muestra: int) -> bool:
    """
    Determina si una mano de 3 cartas tiene flor.

    Args:
        mano          : lista de 3 tuplas (palo_idx, numero)
        palo_muestra  : índice del palo de la muestra (0-3)
        numero_muestra: número de la muestra (el 12 del palo actúa como ella)

    Returns:
        True si tiene flor.
    """
    conteo = Counter(c[0] for c in mano)

    # a) Flor derecha: 3 del mismo palo
    if max(conteo.values()) == 3:
        return True

    # Contar piezas (el 12 del palo de la muestra cuenta como la muestra)
    n_piezas = sum(1 for (p, n) in mano if es_pieza(p, n, palo_muestra, numero_muestra))

    # c) 2 o más piezas
    if n_piezas >= 2:
        return True

    # b) 1 pieza + las otras 2 cartas del mismo palo entre sí
    if n_piezas == 1:
        no_piezas = [p for (p, n) in mano if not es_pieza(p, n, palo_muestra, numero_muestra)]
        if no_piezas[0] == no_piezas[1]:
            return True

    return False


# ---------------------------------------------------------------------------
# Simulación de una mano
# ---------------------------------------------------------------------------


def simular_mano(mazo: list[tuple[int, int]], rng: random.Random) -> dict:
    """
    Baraja el mazo, reparte 3 cartas a cada uno de los 6 jugadores
    y usa la carta 19 (índice 18) como muestra.

    Returns:
        dict con 'flores', 'exito', 'muestra', 'manos'.
    """
    rng.shuffle(mazo)
    muestra = mazo[18]
    palo_muestra, numero_muestra = muestra

    manos = [mazo[i * 3 : (i + 1) * 3] for i in range(6)]
    flores = [tiene_flor(m, palo_muestra, numero_muestra) for m in manos]
    envidos = [calcular_envido(m, palo_muestra, numero_muestra) for m in manos]
    flores_pts = [
        calcular_flor(m, palo_muestra, numero_muestra) if flores[i] else 0
        for i, m in enumerate(manos)
    ]

    flores_A = sum(flores[i] for i in EQUIPO_A)
    flores_B = sum(flores[i] for i in EQUIPO_B)
    exito = flores_A >= 2 or flores_B >= 2

    return {
        "flores": flores,
        "envidos": envidos,
        "flores_pts": flores_pts,
        "exito": exito,
        "muestra": muestra,
        "manos": manos,
    }


# ---------------------------------------------------------------------------
# Simulación principal
# ---------------------------------------------------------------------------


def simular(n: int, seed: int | None = None) -> dict:
    """
    Corre n manos y retorna estadísticas.

    Returns:
        dict con p, ic_low, ic_high, n, breakdown, breakdown_AB, seed.
    """
    rng = random.Random(seed)
    mazo = construir_mazo()

    exitos = 0
    breakdown: Counter[int] = Counter()
    breakdown_AB: Counter[tuple[int, int]] = Counter()

    for _ in range(n):
        r = simular_mano(mazo, rng)
        if r["exito"]:
            exitos += 1
        flores_A = sum(r["flores"][i] for i in EQUIPO_A)
        flores_B = sum(r["flores"][i] for i in EQUIPO_B)
        breakdown[sum(r["flores"])] += 1
        breakdown_AB[(flores_A, flores_B)] += 1

    p = exitos / n
    z = 1.96  # nivel 95%
    se = math.sqrt(p * (1 - p) / n)

    return {
        "n": n,
        "exitos": exitos,
        "p": p,
        "ic_low": max(0.0, p - z * se),
        "ic_high": min(1.0, p + z * se),
        "se": se,
        "breakdown": breakdown,
        "breakdown_AB": breakdown_AB,
        "seed": seed,
    }


def simular_generico(
    n: int,
    success_fn,
    filter_fn=None,
    seed: int | None = None,
) -> dict:
    """
    Motor de simulación genérico.

    filter_fn : si se provee, solo se cuentan manos donde filter_fn(r) es True
                (denominador de probabilidad condicional).
    success_fn: cuenta un éxito dado el resultado r de una mano.

    Returns dict con p, ic_low, ic_high, se, n, n_filtradas, exitos, seed.
    """
    rng = random.Random(seed)
    mazo = construir_mazo()

    n_filtradas = 0
    exitos = 0

    for _ in range(n):
        r = simular_mano(mazo, rng)
        if filter_fn is not None and not filter_fn(r):
            continue
        n_filtradas += 1
        if success_fn(r):
            exitos += 1

    denom = n_filtradas if filter_fn is not None else n
    p = exitos / denom if denom > 0 else 0.0
    z = 1.96
    se = math.sqrt(p * (1 - p) / denom) if denom > 0 else 0.0

    return {
        "n": n,
        "n_filtradas": n_filtradas,
        "exitos": exitos,
        "p": p,
        "ic_low": max(0.0, p - z * se),
        "ic_high": min(1.0, p + z * se),
        "se": se,
        "seed": seed,
    }
