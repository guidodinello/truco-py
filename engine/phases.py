from enum import IntEnum


class Phase(IntEnum):
    FLOR = 0  # flor bidding (skipped if no one has flor)
    ENVIDO = 1  # envido bidding (skipped if anyone has flor)
    TRUCO = 2  # truco bidding (simplified: happens before card play)
    PLAY = 3  # card play (3 tricks)
    DONE = 4  # hand complete
