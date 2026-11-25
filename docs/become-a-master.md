# Become a master

A training plan for reading the cards in 3v3 truco uruguayo: knowing, with high
probability, one or two cards each player holds, from card logic alone. Four weeks at
about 15 minutes a day, then real games carry it.

Out of scope: reading people (señas, tells, betting behavior, profiling). That's a
different skill set.

## The six techniques

1. **Clump tracking (paquete):** carrying an ordered group of cards across a weak
   shuffle into the next hand.
2. **Shown-card tracking:** a perfect tally of what has been revealed this hand.
3. **Envido/flor inference:** turning a declared score into the hands that could
   produce it.
4. **Elimination:** combining everything known to narrow each hand down to a few
   candidates.
5. **Play logic:** which hands make a given card choice sensible.
6. **Probability estimation:** quick odds when the facts run out
   ([cheat sheet](#cheat-sheet-3v3) below).

## Foundations

Every technique assumes the rules math is instant. Move on when you can do 50 random
deals in a row at under 3 seconds each, with no errors.

- **Piezas on sight:** given the muestra, name the five piezas: 2, 4, 5, 11, 10 of its
  suit. If the muestra is one of those, the 12 of that suit takes its place.
- **Envido of any three cards:**
  - With a pieza: its value (2→30, 4→29, 5→28, 11/10→27) plus the highest other card.
  - Two of the same suit: 20 plus both cards.
  - Otherwise: the highest single card.
  - Figures (10, 11, 12) count 0 unless they are piezas.
- **Flor on sight:** three of the same suit, two or more piezas, or one pieza plus two of
  the same suit.

**Drill:** deal 3 cards plus a muestra, say the envido out loud and whether it's flor,
then check. Time the whole set.

## Technique drills

Envido inference and shown-card tracking pay off the most per minute; play logic the
least.

### 1. Clump tracking (paquete)

- **Shuffle audit (do this first):** put 2-3-4-5 of oro together, do your real table
  shuffle, cut, deal six hands plus the muestra. Record whether 3+ stayed adjacent and
  where they landed. After 20 reps you know your own survival rate, which tells you how
  far to trust a paquete. A cut alone rarely breaks a 4-card block (about 1 cut in 13);
  the shuffle is what does.
- **Prediction drill:** build the paquete, 2 minutes of distraction (a podcast, counting
  back by 7), then shuffle, cut, deal. From your 3 cards and the muestra, call who got
  the rest: cards dealt one at a time land on consecutive seats. Reveal and score.
- **Levels:** 3 same-suit in sequence → 4 → mixed suits built on the matas (1 espada,
  1 basto, 7 espada, 7 oro) → two paquetes at once.
- **Move on when:** you recall the paquete every time, and when it survived, your calls
  are right 9 times out of 10.

### 2. Shown-card tracking

- **Drill:** shuffle, then flip cards one at a time to a metronome (one card per 2 s).
  Stop at a random point and answer: which piezas and matas have not appeared yet?
- **Levels:** 6 cards → 19 cards (a full 3v3 deal plus muestra) → flip the muestra
  first, so the pieza set changes every round → one card per second → while talking.
- **Move on when:** no misses on 19 cards at one card per second.

### 3. Envido/flor inference

Where a declared score is ambiguous:

| Declared envido | What it means |
| --- | --- |
| 34–37 | Has a pieza, for sure |
| 27–33 | Pieza, or two of the same suit: ambiguous |
| 20–26 | Two of the same suit, no pieza |
| 0–7 | Three different suits, no pieza |

- **Drill:** flashcards of muestra + declared score; list every way to make it. Example:
  muestra 6 of oro, «33» = 7+6 of copa, espada or basto; or 2 of oro + 3; 4 of oro + 4;
  5 of oro + 5; 11 or 10 of oro + 6.
- **Levels:** list the options → cross out what your own cards and the muestra rule
  out → also use cards already played → do it during the call, before answering.
- **Move on when:** a complete, pruned list in under 20 seconds.

### 4. Elimination

- **Drill:** deal a full hand face up, play it out alone by turns, but take the view of
  one seat. After each baza, write each hidden hand's candidates from what that seat
  could know (calls, cards shown). Check against the real hands. In 3v3 start with the
  two opponents next to you, then widen.
- **At the table:** after each hand, before the cards are collected, say your read of
  one opponent's hand and check it.
- **Move on when:** the true hand is in your candidate list 9 times out of 10, and the
  lists keep shrinking.

### 5. Play logic

- **Drill:** review hands (yours, or games between this repo's agents) and for each
  card played ask which hands make that play sensible. Example: tying the first baza
  (empardar) usually means a strong card held back for the second.
- Lowest priority: start it once 1–4 feel automatic.

### 6. Probability estimation

- **Drill:** say your estimate out loud first («I hold no pieza, chance an opponent
  has one?»), then check the cheat sheet.
- **Move on when:** your guesses land within 10 points.

## Cheat sheet (3v3)

Generated by `uv run python scripts/cheatsheet.py` (300,000 deals, seed 42). Envido
counts ties as not beaten and doesn't separate flor hands.

### Piezas

| Situation | Probability |
| --- | --- |
| You hold a pieza | 35% |
| You hold none: a given other player has one | 37% |
| You hold none: at least one of your 2 partners has one | 62% |
| You hold none: at least one of the 3 opponents has one | 79% |

### Envido

With three opponents, 32 is the coin flip:

| Your envido | P(an opponent has more) |
| --- | --- |
| 25 | 93% |
| 26 | 91% |
| 27 | 86% |
| 28 | 81% |
| 29 | 76% |
| 30 | 68% |
| 31 | 59% |
| 32 | 50% |
| 33 | 36% |

Your own hand reaches 33+ in 20% of deals, 30+ in 36%, and 27+ in 53%.

### Pico a pico

In pico a pico the piezas go «por abajo»: a face-down card in an earlier pico is a
pieza, identity unknown. The count is enough for the odds. With no pieza in your hand:

| Your pico | Cards shown before | 0 tapadas | 1 tapada | 2 tapadas |
| --- | --- | --- | --- | --- |
| 1 | 0 | 37% | — | — |
| 2 | 6 | 43% | 36% | 28% |
| 3 | 12 | 52% | 44% | 34% |

Clean cards in earlier picos make your rival likelier to hold one; tapadas make it less
likely. Real picos often end before all six cards are shown, so actual odds sit a bit
closer to 37%. The engine doesn't model this information yet
([#88](https://github.com/guidodinello/truco-py/issues/88)).

## Tooling ideas

The engine can generate and grade most drills instead of doing them by hand:

| Tool | What it does | Builds on |
| --- | --- | --- |
| `drill envido` | Shows muestra + declared score; you list the hands; it grades completeness | `engine.truco` envido/flor scoring |
| `drill shown` | Flashes cards on a timer, then asks which piezas and matas are unseen | Deck, muestra logic |
| `drill elim` | Plays a hand from one seat's view; you name candidates; it reveals the true set | Determinized agent's hand sampler |
| Shuffle model | Simulates k riffles + a cut to estimate paquete survival by shuffle count | New |
| Conditional tables | P(opponent > X given I have Y) over a full grid | `experimentos/experimento_envido.py` |

## Schedule

| Week | Focus | Daily drills |
| --- | --- | --- |
| 1 | Foundations + your shuffle | Foundations set; shuffle audit (20 reps total) |
| 2 | Seeing and decoding | Shown-card tracking; envido flashcards |
| 3 | Putting it together | Elimination replays; paquete level 2 |
| 4 | Under load | Everything while talking; probability guesses; play-logic review |
