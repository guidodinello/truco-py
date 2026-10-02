from enum import IntEnum


class Phase(IntEnum):
    FLOR = 0  # flor contest between the two sides' flor holders (before any card)
    ENVIDO = 1  # an envido call is waiting for an answer
    TRUCO = 2  # a truco / retruco / vale cuatro call is waiting for an answer
    PLAY = 3  # a player's turn in a trick: play a card, call, or leave
    DONE = 4  # hand complete
    LEY = 5  # «a ley de juego»: imposing the régimen, or answering it
