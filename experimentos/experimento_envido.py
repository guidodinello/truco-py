"""
Experimento: P(al menos un oponente tiene > X puntos de envido | yo tengo exactamente Y)

Editar los parámetros de abajo para cada nueva pregunta.
"""

from engine.truco import EQUIPO_B, simular_generico
from report import imprimir_resultado_generico

# ---------------------------------------------------------------------------
# Parámetros — ajustar según la pregunta
# ---------------------------------------------------------------------------

YO = 0  # índice del jugador "yo" (0-based); EQUIPO_A = [0, 2, 4]
X = 30  # umbral de envido del oponente
Y = 30  # mi puntaje de envido (condición)


def _simulate(n, seed):
    return simular_generico(
        n,
        success_fn=lambda r: any(r["envidos"][i] > X for i in EQUIPO_B),
        filter_fn=lambda r: r["envidos"][YO] == Y,
        seed=seed,
    )


def _report(r):
    print(f"\n  Pregunta: P(algún oponente > {X} puntos | yo tengo exactamente {Y})")
    imprimir_resultado_generico(r)


EXPERIMENTO = {
    "description": (
        f"Simulación Monte Carlo — Envido en Truco Uruguayo\n"
        f"P(algún oponente > {X} puntos | yo tengo exactamente {Y})"
    ),
    "simulate": _simulate,
    "report_fn": _report,
}
