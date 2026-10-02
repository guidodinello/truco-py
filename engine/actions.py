from enum import IntEnum

from .truco import NUMEROS


class Action(IntEnum):
    # Answers to a pending call (envido, flor envite, truco, a ley de juego)
    FOLD = 0  # «no quiero»
    QUIERO = 1  # «quiero» — accept the pending call (all of it, under a ley de juego)

    # Flor contest: decline to make an envite, flors are compared as they stand
    FLOR_PASS = 2

    # Envites. The same calls are made «con flor» in a flor contest (S2 Art 27).
    ENVIDO = 3  # 2 tantos
    REAL_ENVIDO = 4  # 3 tantos
    DOS_REAL_ENVIDO = 5  # 2 × 3 tantos (S2 Art 24 multiplier)
    TRES_REAL_ENVIDO = 6  # 3 × 3 tantos
    HASTA_IGUALAR = 7  # the tantos that level the caller's side with the leader (S2 Art 24)
    FALTA_ENVIDO = 8  # the falta (S2 Art 25)
    CONTRA_FLOR_AL_RESTO = 9  # flor contest only: the resto, contra flor (S2 Art 31, 33)

    # Truco ladder (S1 Art 42–47, S2 Art 60–66)
    TRUCO = 10
    RETRUCO = 11
    VALE_CUATRO = 12

    # Leaving the hand (S2 Art 88–90)
    PASO = 13  # «paso»: this player is out, teammates play on
    MAZO = 14  # to the mazo without «paso»: the whole side is out

    # «A ley de juego» (S2 Art 70–82): the bundle imposed before the muestra
    LEY_PASS = 15  # do not impose the régimen
    LEY_TODO = 16  # «todo dicho»: falta envido, resto and truco
    LEY_FALTA = 17
    LEY_RESTO = 18
    LEY_FALTA_RESTO = 19
    LEY_FALTA_TRUCO = 20
    LEY_TRUCO = 21
    LEY_RESTO_TRUCO = 22
    # Partial answers to a ley de juego (S2 Art 75); QUIERO / FOLD answer all of it
    LEY_QUIERO_ENVITE = 23
    LEY_QUIERO_TRUCO = 24

    # Card play: 40 cards, card_idx = palo * 10 + NUMEROS.index(numero)
    PLAY_CARD_0 = 25
    PLAY_CARD_1 = 26
    PLAY_CARD_2 = 27
    PLAY_CARD_3 = 28
    PLAY_CARD_4 = 29
    PLAY_CARD_5 = 30
    PLAY_CARD_6 = 31
    PLAY_CARD_7 = 32
    PLAY_CARD_8 = 33
    PLAY_CARD_9 = 34
    PLAY_CARD_10 = 35
    PLAY_CARD_11 = 36
    PLAY_CARD_12 = 37
    PLAY_CARD_13 = 38
    PLAY_CARD_14 = 39
    PLAY_CARD_15 = 40
    PLAY_CARD_16 = 41
    PLAY_CARD_17 = 42
    PLAY_CARD_18 = 43
    PLAY_CARD_19 = 44
    PLAY_CARD_20 = 45
    PLAY_CARD_21 = 46
    PLAY_CARD_22 = 47
    PLAY_CARD_23 = 48
    PLAY_CARD_24 = 49
    PLAY_CARD_25 = 50
    PLAY_CARD_26 = 51
    PLAY_CARD_27 = 52
    PLAY_CARD_28 = 53
    PLAY_CARD_29 = 54
    PLAY_CARD_30 = 55
    PLAY_CARD_31 = 56
    PLAY_CARD_32 = 57
    PLAY_CARD_33 = 58
    PLAY_CARD_34 = 59
    PLAY_CARD_35 = 60
    PLAY_CARD_36 = 61
    PLAY_CARD_37 = 62
    PLAY_CARD_38 = 63
    PLAY_CARD_39 = 64


CARD_OFFSET = Action.PLAY_CARD_0.value
N_ACTIONS = len(Action)

ENVIDO_CALLS = (
    Action.ENVIDO,
    Action.REAL_ENVIDO,
    Action.DOS_REAL_ENVIDO,
    Action.TRES_REAL_ENVIDO,
    Action.HASTA_IGUALAR,
    Action.FALTA_ENVIDO,
)
ENVITE_CALLS = (*ENVIDO_CALLS, Action.CONTRA_FLOR_AL_RESTO)
TRUCO_CALLS = (Action.TRUCO, Action.RETRUCO, Action.VALE_CUATRO)
LEY_BUNDLES = (
    Action.LEY_TODO,
    Action.LEY_FALTA,
    Action.LEY_RESTO,
    Action.LEY_FALTA_RESTO,
    Action.LEY_FALTA_TRUCO,
    Action.LEY_TRUCO,
    Action.LEY_RESTO_TRUCO,
)


def card_to_action(palo: int, numero: int) -> Action:
    """Convert (palo_idx, numero) to the corresponding PLAY_CARD action."""
    idx = palo * 10 + NUMEROS.index(numero)
    return Action(CARD_OFFSET + idx)


def action_to_card(action: Action) -> tuple[int, int]:
    """Convert a PLAY_CARD action to (palo_idx, numero)."""
    idx = action.value - CARD_OFFSET
    palo = idx // 10
    numero = NUMEROS[idx % 10]
    return (palo, numero)


def is_card_action(action: Action) -> bool:
    return action.value >= CARD_OFFSET
