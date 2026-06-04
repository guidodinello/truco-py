from enum import IntEnum

from .truco import NUMEROS


class Action(IntEnum):
    FOLD = 0  # give up current bid (opponent wins stake)

    # Flor bidding
    FLOR_PASS = 1  # accept current flor stake / pass without bidding
    FLOR_CHICO = 2  # announce flor for 3 pts
    FLOR_CON_ENVIDO = 3  # raise flor to 5 pts
    FLOR_CONTRA_RESTO = 4  # game-ending flor bid

    # Envido bidding
    ENVIDO_PASS = 5  # pass (no bid) OR accept current envido stake
    ENVIDO = 6  # bid envido (+2 pts to stake)
    REAL_ENVIDO = 7  # bid real envido (+3 pts to stake)
    FALTA_ENVIDO = 8  # game-ending envido bid

    # Truco bidding
    TRUCO_PASS = 9  # pass (no bid) OR accept current truco stake
    TRUCO = 10  # bid truco (2 pts)
    RETRUCO = 11  # raise to 3 pts
    VALE_CUATRO = 12  # raise to 4 pts

    # Card play: 40 cards
    # card_idx = palo * 10 + NUMEROS.index(numero)
    PLAY_CARD_0 = 13
    PLAY_CARD_1 = 14
    PLAY_CARD_2 = 15
    PLAY_CARD_3 = 16
    PLAY_CARD_4 = 17
    PLAY_CARD_5 = 18
    PLAY_CARD_6 = 19
    PLAY_CARD_7 = 20
    PLAY_CARD_8 = 21
    PLAY_CARD_9 = 22
    PLAY_CARD_10 = 23
    PLAY_CARD_11 = 24
    PLAY_CARD_12 = 25
    PLAY_CARD_13 = 26
    PLAY_CARD_14 = 27
    PLAY_CARD_15 = 28
    PLAY_CARD_16 = 29
    PLAY_CARD_17 = 30
    PLAY_CARD_18 = 31
    PLAY_CARD_19 = 32
    PLAY_CARD_20 = 33
    PLAY_CARD_21 = 34
    PLAY_CARD_22 = 35
    PLAY_CARD_23 = 36
    PLAY_CARD_24 = 37
    PLAY_CARD_25 = 38
    PLAY_CARD_26 = 39
    PLAY_CARD_27 = 40
    PLAY_CARD_28 = 41
    PLAY_CARD_29 = 42
    PLAY_CARD_30 = 43
    PLAY_CARD_31 = 44
    PLAY_CARD_32 = 45
    PLAY_CARD_33 = 46
    PLAY_CARD_34 = 47
    PLAY_CARD_35 = 48
    PLAY_CARD_36 = 49
    PLAY_CARD_37 = 50
    PLAY_CARD_38 = 51
    PLAY_CARD_39 = 52


CARD_OFFSET = Action.PLAY_CARD_0.value  # 13
N_ACTIONS = 53


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
