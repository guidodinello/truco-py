"""
Truco card strength hierarchy (strongest → weakest):

  Piezas  (muestra-dependent, ranks 14-18):
    2 muestra (30 envido) > 4 muestra > 5 muestra > 11 muestra > 10 muestra

  Matas (fixed, ranks 9-13):
    1 Espadas > 1 Bastos > 7 Espadas > 7 Oros

  Chicas (ranks 7-9):
    any 3 > non-pieza 2 > 1 Copas / 1 Oros

  Negras (non-pieza, ranks 4-6):
    12s > 11s > 10s

  Comunes (ranks 0-3):
    7 Bastos / 7 Copas > 6s > non-pieza 5s > non-pieza 4s

Equal-strength cards tie the trick (va parda).
"""

from .truco import es_pieza

_PIEZA_STRENGTH = {2: 18, 4: 17, 5: 16, 11: 15, 10: 14}


def card_strength(palo: int, numero: int, palo_muestra: int, numero_muestra: int) -> int:
    """Return truco strength in [0, 18]. Higher = stronger."""
    # Piezas (muestra-dependent)
    if es_pieza(palo, numero, palo_muestra, numero_muestra):
        n_ef = numero_muestra if numero == 12 else numero
        return _PIEZA_STRENGTH[n_ef]

    # Matas (fixed regardless of muestra)
    if palo == 0 and numero == 1:
        return 13  # 1 Espadas
    if palo == 1 and numero == 1:
        return 12  # 1 Bastos
    if palo == 0 and numero == 7:
        return 11  # 7 Espadas
    if palo == 3 and numero == 7:
        return 10  # 7 Oros

    # Chicas
    if numero == 3:
        return 9  # any 3
    if numero == 2:
        return 8  # non-pieza 2
    if numero == 1:
        return 7  # 1 Copas or 1 Oros

    # Negras (non-pieza 10, 11, 12)
    if numero == 12:
        return 6
    if numero == 11:
        return 5
    if numero == 10:
        return 4

    # Comunes
    if numero == 7:
        return 3  # 7 Bastos or 7 Copas
    if numero == 6:
        return 2
    if numero == 5:
        return 1
    if numero == 4:
        return 0

    raise ValueError(f"Unknown card: palo={palo}, numero={numero}")
