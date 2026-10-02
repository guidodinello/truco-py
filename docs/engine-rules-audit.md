# Engine rules audit

Audit of the engine (`engine/game.py`, `engine/card.py`, `engine/truco.py`) against
[`rules.md`](rules.md). **Docs only — nothing in the engine was changed.** Source IDs (`S1`…`S7`)
and the SB/CP tags are defined in `rules.md`; every quotation below was checked against the saved
source texts.

- Engine code read at `origin/main` = `64a1ce4`. `engine/` is byte-identical on
  `exp/rebenchmark-seat-rotated`, so the line numbers hold on both.
- Behaviour claims were **executed**, not just read: read-only scripts importing the engine from the
  main checkout (no engine edits, no installs). Observed outputs are quoted in each finding.
- Frequencies come from 200 000 deals through `engine.truco.simular_mano` (seed 12345) and 20 000
  random-play hands; see [Appendix A](#appendix-a--reproduction-scripts).
- Severity uses the four levels requested: **illegal action allowed**, **legal action missing**,
  **wrong payout**, **cosmetic**.
- Mano is always seat 0 (team A: seats 0, 2, 4; team B: 1, 3, 5): `game.py:226-230`,
  `game_state.py` `TEAM_A/TEAM_B`. Seat rotation is done by the harness, not the engine
  (`scripts/benchmark.py` team-slot mapping). "Mano wins" in the engine therefore means "seat 0 /
  team A wins".

## Summary

| ID | Discrepancy | file:line | Severity | Can it change training / benchmark results? | Issue |
|---|---|---|---|---|---|
| A-01 | Flor raises gated on the numeric stake: contra flor al resto is not terminal and the ladder goes **backwards** (5 → 3), so hands never end | `game.py:252-255`, `:286-289` | illegal action allowed | **Yes.** Non-terminating hands; exp 008 voids ≈4 in 100 matches for thr2M (#7) | [#7](https://github.com/guidodinello/truco-py/issues/7) |
| A-02 | Contra flor al resto pays the **last bidder's own** shortfall, not the leader's; paid to whichever side wins | `game.py:289` (doc claim at `:11`) | wrong payout | **Yes.** Up to a 30-point swing on one hand; can decide a match | [#7](https://github.com/guidodinello/truco-py/issues/7) |
| A-03 | `VALE_CUATRO` legal directly in answer to a plain `TRUCO` (skips retruco) | `game.py:437-438` | illegal action allowed | **Yes.** Every truco; uniform-random agents take it ~1 time in 4 | [#8](https://github.com/guidodinello/truco-py/issues/8) |
| A-04 | Envido raises have no falta cap and no bound: stake can pass the falta and the target; chains never have to end | `game.py:331-337`, `:397-402`, `:417` | wrong payout (overshoot); liveness hazard | **Possibly.** Overshoot only matters near the target; unbounded chains are the same class as A-01 | [#9](https://github.com/guidodinello/truco-py/issues/9) |
| A-05 | Envido tie always goes to team A, not to the side that declares the tied figure first | `game.py:412-413` | wrong payout | **Yes, small.** Engine ≠ declaration procedure in 3.2 % of no-flor deals (≈1.1 % of all deals) when envido is accepted | [#10](https://github.com/guidodinello/truco-py/issues/10) |
| A-06 | Flor tie always goes to team A (same class as A-05); comment at `:305` contradicts the code | `game.py:305-307` | wrong payout | **Yes, small.** 519 in 200 000 deals (1.7 % of contested flors) | [#7](https://github.com/guidodinello/truco-py/issues/7) |
| A-07 | Two pardas then team B wins trick 3 → hand awarded to team A | `game.py:609-630` (fall-through `:630`) | wrong payout (wrong hand winner) | **Yes, rare.** ≈0.03 % of random-play hands | [#11](https://github.com/guidodinello/truco-py/issues/11) |
| A-08 | Contested flor pays a flat 3 (or 5) regardless of how many flors the winning side holds | `game.py:275`, `:297-307`, `:285` | wrong payout | **Yes.** ≥2 flors on a side in ≈25 % of contested flors (≈3.9 % of all deals) | [#7](https://github.com/guidodinello/truco-py/issues/7) |
| A-09 | `FOLD` is a legal answer to a plain flor announcement (la mía flor) | `game.py:251` | illegal action allowed | Negligible for rational agents; adds a dominated action | [#7](https://github.com/guidodinello/truco-py/issues/7) |
| A-10 | No «con flor» real envido / falta envido (ladder has only CHICO, CON_ENVIDO(5), CONTRA_RESTO) | `game.py:244-256`, `actions.py:15-18` | legal action missing (**variant-dependent**: S3 lists only three calls) | Restricts the action space; no outcome error | [#7](https://github.com/guidodinello/truco-py/issues/7) |
| A-11 | No «irse al mazo» / «pasar» during card play | `game.py:127-128` | legal action missing (undocumented) | **Yes.** A real strategic action is absent | [#12](https://github.com/guidodinello/truco-py/issues/12) |
| A-12 | Truco/retruco/vale cuatro only in a phase *before* the first card; the «quiero» side can never re-raise later | `game.py:8`, `:222-230`, `:485-487` | legal action missing (documented) | **Yes** by construction: no truco calls informed by trick results | tracking [#13](https://github.com/guidodinello/truco-py/issues/13) |
| A-13 | Only the first flor holder per team bids; only the first opposing player answers envido/truco; all 6 players get an opening turn in seat order | `game.py:5-7`, `:187-190`, `:361-367`, `:469-473` | legal action missing (documented) | **Yes** by construction | tracking [#13](https://github.com/guidodinello/truco-py/issues/13) |
| A-14 | 6-player pico a pico / redondilla alternation, malas/buenas, chicos not implemented; single game to 40 | `game.py:9`, `:49` | legal action missing (documented); variant | By construction: benchmarks are all-redondilla | tracking [#13](https://github.com/guidodinello/truco-py/issues/13) |
| A-15 | Echar los perros / «a ley de juego», real-envido multiplier, «hasta igualar», envido + truco in one breath not implemented | — | legal action missing (undocumented; variant-dependent) | By construction | tracking [#13](https://github.com/guidodinello/truco-py/issues/13) |
| A-16 | Docstring / comment errors: `:11` says the resto uses the *winner's* score; `:305` says a flor tie awards nothing and then awards team A; `:244` dead `if True:`; `:258` unreachable branch | `game.py:11`, `:244`, `:258`, `:305` | cosmetic | No | folded into A-02 / A-06 |
| R-01 | *(not a rules item)* `reset(seed=…)` is not deterministic on a reused `TrucoGame` | `game.py:51,60`, `truco.py:155` | — | Hand-level seeds do not replay a hand | not filed — see Appendix B |

### Checked and matching the spec (no discrepancy)

So the table is not read as "everything is wrong". The first three items were checked
**empirically** against an independent implementation of the S1/S2 tables
([Appendix A](#appendix-a--reproduction-scripts)): hierarchy over all 40 possible muestras × all 780
card pairs, **0 mismatches**; envido/flor detection and points over 300 000 random hands (46 431
flor, 253 569 envido), **0 mismatches**; hand winner over all 27 trick sequences, **1 mismatch**
(`[parda, parda, B]` = A-07). The rest were checked by reading.

- Card hierarchy (`card.py`) = S1 Art 8 / S2 Art 12 for every category and within-category order,
  including the 12-as-pieza rule (`truco.py:es_pieza`).
- Envido card values and hand scores (`truco.py:valor_envido_carta`, `calcular_envido`) = S1 Art
  9–10B / S2 Art 13–14B for every case (one pieza; two same-suit; three suits; negras).
- Flor detection and flor scoring (`tiene_flor`, `calcular_flor`) = S1 Art 10A, 11 / S2 Art 14A, 15
  (three piezas, two + any, one + two same suit, three same suit; max 47).
- Falta = `target - max(scores)` (`game.py:405`) = leader's shortfall: S3 L109, S2 Art 25.
- Declined first envido = 1; declined raise = the sum already accepted; accepted = the sum
  (`game.py:373`, `:398-402`): S3 L113–121, S2 Art 24, 35.
- Truco no-quiero payouts 1 / 2 / 3 (`game.py:478`, `max(stake - 1, 1)`) and accepted 2 / 3 / 4:
  S1 Art 43–47.
- Truco alternation (the raiser cannot raise its own call): S4, S1 Art 45.
- One-sided flor pays 3 per flor and skips envido (`game.py:177-183`, `:163-166`): S3 L134, L146.
- Trick resolution, parda → mano leads, hand winner for every trick sequence **except**
  `[parda, parda, B]` (A-07), and all-tie → mano (valid because seat 0 is mano): S1 Art 39–41.

---

## Findings

### A-01 — Flor raises gated on the numeric stake (issue #7, part a)

**Engine.** `_flor_legal` (`game.py:236-259`) decides raises from `state.flor_stake`:
`if stake < 5` → `FLOR_CON_ENVIDO` (`:252-253`); `if stake < 9999` → `FLOR_CONTRA_RESTO` (`:254-255`,
always true). `FLOR_CONTRA_RESTO` sets `flor_stake = target - scores[my_team]` (`:289`), which can
be anything from 1 to 40. So:

1. `CONTRA_RESTO` is always available to the answering side, including against another
   `CONTRA_RESTO`: nothing ends the exchange.
2. When the resto is small (< 5), `CON_ENVIDO` becomes legal *again* after `CONTRA_RESTO`, and
   re-raising to `CON_ENVIDO` lowers the stake (resto → 5).

**Spec.** The resto *is* the falta and cannot be exceeded (S2 Art 33: «La palabra "resto" equivale
a la "falta"»; Art 36 cap), so contra flor al resto tops the ladder; nothing re-raises it
(**inferred** from the cap — no source says so in words; `rules.md` §4.4). The ladder order is
la mía flor < con flor envido < contra flor al resto (S3 L138–142).

**Repro (observed).**

```
scores [37, 0]; every action below was returned by legal_actions:
FLOR_CONTRA_RESTO->stake 3 · FLOR_CON_ENVIDO->stake 5 · FLOR_CONTRA_RESTO->stake 3 ·
FLOR_CON_ENVIDO->stake 5 · … (8 raises, phase still FLOR)
scores [0, 0]: 10 consecutive FLOR_CONTRA_RESTO, phase still FLOR,
legal now: ['FOLD', 'FLOR_PASS', 'FLOR_CONTRA_RESTO']
```

**Impact.** Non-terminating hands; reproduces the exp 008 loop in issue #7. Any agent that prefers
raising over answering can hold a hand open indefinitely. The harness works around it by voiding
hands over 2000 actions.

### A-02 — Contra flor al resto amount (issue #7, part b)

**Engine.** `game.py:289`: `state.flor_stake = state.target - state.scores[my_team]`, where
`my_team` is the team **making the bid**. `_resolve_flor` then pays that fixed number to
whichever team wins the flor comparison (`:297-307`). The module docstring (`:11`) says the
resto pays `target - winner's current score`; the code does not.

**Spec.** The resto is the *leader's* shortfall: S3 L142 «los puntos que le faltan al que vaya
ganando para terminar el partido al igual que en la falta envido»; S2 Art 33 + Art 25. Variant S4:
the winner «gana el Partido» ([V-01](rules.md#10-variants-register)). The engine matches neither
reading except when the bidder is the leader.

**Repro (observed).** Same score line `[30, 10]`, target 40; leader's shortfall = 10:

```
bidder team 0 (leader)  -> flor_stake 10
bidder team 1 (trailing) -> flor_stake 30
```

The amount depends on who bids. A trailing bidder who wins the flor gets +30 (the whole match,
from 10 to 40) where the spec says 10; and if the leader wins against that bid, the leader is also
paid 30 when only 10 are needed (harmless overshoot). The bidder's own score should not matter.

**Impact.** Largest payout error in the audit; reachable on every contested flor (≈15 % of deals
have flor on both teams). An RL agent is rewarded for contra flor al resto from behind.

### A-03 — `VALE_CUATRO` directly over `TRUCO`

**Engine.** `_truco_legal` (`game.py:432-439`), responder branch: `if stake == 2` → `RETRUCO`;
`if stake <= 3` → `VALE_CUATRO`. At `stake == 2` both hold, so `VALE_CUATRO` is offered against a
plain truco. (The same-team branch `:441-447` has the same `<= 3` but is unreachable: each raise
hands the turn to the opposing side.)

**Spec.** Valid answers to truco are «a) No quiero. b) Quiero. c) Retruco.» (S1 Art 42; S2 Art 60);
vale cuatro is only the answer to a retruco (S1 Art 45: «cuyo inciso c) dirá "vale cuatro"»; Art 46
«Si al contestarse el "retruco" …»). S4: ladders alternate; S3 L91 describes the same sequence.

**Repro (observed).**

```
legal vs TRUCO: ['FOLD', 'TRUCO_PASS', 'RETRUCO', 'VALE_CUATRO']
stake after VALE_CUATRO on TRUCO: 4
```

**Impact.** Any hand where truco is called. A responder can leap from 2 to 4 with one action and
the caller can only fold (paying 3: `game.py:478`) or accept. Uniform-random agents choose it ~1
time in 4 when answering a truco.

### A-04 — Envido raises: no falta cap, no bound

**Engine.** After any non-falta bid the responder always has `ENVIDO`, `REAL_ENVIDO`, `FALTA_ENVIDO`
(`game.py:331-337`); `ENVIDO` adds 2, `REAL_ENVIDO` adds 3 (`:397-402`) with no ceiling, and
acceptance pays `max(stake, 2)` (`:417`). Only the explicit `FALTA_ENVIDO` is capped
(`target - max(scores)`, `:405`).

**Spec.** Raises may be repeated at will (S1 Art 26; S2 Art 35: «Los reenvites pueden ser
repetidos tantas veces como se desee»), **but** are capped at the falta: S2 Art 36: «Si en un
envite el envidante excede la falta … ese envite se tomará como simple de dos tantos. En caso de
ser excedida la falta en virtud de un reenvite, éste será siempre válido por el importe del envite
o reenvite que le precede o por la falta si fuera ésta menor».

**Repro (observed).** scores `[38, 30]` (falta = 2):

```
after 21 chained ENVIDO: stake = 42, phase = ENVIDO, ENVIDO still legal: True
```

**Impact.** (i) *Payout:* a stake above the falta/target is paid in full; matters only near the
end of a game. (ii) *Liveness:* repeated raises are legal in the real game too, so this is not an
illegal action, but the engine has no cap at all: the same shape as A-01, and a deterministic
agent can keep a hand open forever. Which fix (cap at falta, cap at a number of raises, or both) is
a design decision, not a rules one.

### A-05 — Envido tie goes to team A

**Engine.** `_envido_winner` (`game.py:408-414`): `if max_A >= max_B: return 0` — the comment says
«mano (team A) wins ties».

**Spec.** Figures are declared by a turn-taking procedure: mano declares, then a *rival* of the
last declarer declares only if their figure **beats** it, and so on; equal does not beat (S2 Art 39:
«El rival que lo supere empezando por su derecha, cantará el suyo …»; Art 44: «cante cifra igual o
inferior a la cantada por un rival de su izquierda, no pudiendo cantar válidamente su punto»). A tie
therefore goes to **the side that declared the tied figure first in that procedure**, which is not
always team A (`rules.md` §3.5; inferred for teams, stated outright for 1v1 by S5: «En caso de
empate, gana el jugador que es mano»). It is also *not* "the lowest seat holding the maximum": with
figures `[30, 20, 33, 33, …]` in seat order, seat 3 (B) declares 33 first (seat 2 is a teammate of the
last declarer and never speaks), so B wins.

**Repro (observed).** Envidos by seat `[6, 33, 33, 7, 5, 28]`: seat 0 (A) declares 6; seat 1 (B)
beats it with 33; seat 2 (A) only ties, so does not speak — B wins. After `ENVIDO` + accept the
engine gives `hand_pts == [2, 0]`: team A is paid.

**Frequency (procedure simulated over 200 000 deals).** Of 68 420 no-flor deals, 4 928 (7.20 %) tie on
the maximum. The engine's winner differs from the procedure's in **2 191 (3.20 % of no-flor deals,
≈1.1 % of all deals)** under reading (a) of Art 39 and 2 184 under reading (b)
([V-14](rules.md#10-variants-register)): the finding does not depend on how that ambiguity is
resolved. It only matters if envido is called and accepted.

**Impact.** Extra tie-wins for team A: a seat-position artefact. In seat-rotated benchmarks it
cancels in aggregate (team A is rotated); in training it is a spurious advantage for even seats on
equal-value hands.

### A-06 — Flor tie goes to team A (issue #7 comment)

**Engine.** `_resolve_flor` (`game.py:297-307`): `else: state.hand_pts[0] += pts  # mano (player 0,
team A) wins ties`; the comment two lines above says «Tie: no pts awarded».

**Spec.** The flor «del equipo en que sea más mano el jugador que cante» wins a tie (S2 Art 20;
S1 Art 14: «ganará la del jugador que sea mano»), with figures declared by the same procedure (S2
Art 40). Same argument as A-05.

**Frequency.** 30 523 deals (15.3 %) have flor on both sides; 1 505 of those tie (4.9 %); the engine
differs from the procedure in **519 (1.70 % of contested flors, 0.26 % of all deals)** under either
reading of Art 39.

### A-07 — `[parda, parda, B]` awards the hand to team A

**Engine.** `_compute_hand_winner` (`game.py:609-630`) handles ≥2 trick wins and the two
`[A,B,parda]` / `[B,A,parda]` cases, then falls through: `return 0` (`:630`, comment «All ties →
mano»). `[-1, -1, 1]` (two pardas, then team B wins trick 3) reaches that line.

**Spec.** «El que gane la tercera si las dos anteriores fueron "pardas"» (S1 Art 41c; S2 Art 59c;
S3 table L80: Empate, Empate, A → A). Only all-three-parda goes to mano.

**Repro (observed).** `trick_winners = [-1, -1, 1]` → `_compute_hand_winner(...) == 0`
(spec: B); `[-1, -1, 0]` → 0 (correct by coincidence).

**Frequency.** Uniform-random play (bidding phases declined), 20 000 hands: 10 (0.05 %) start with
two pardas, 5 (0.03 %) of them are won by B on trick 3 and are awarded to A.

### A-08 — Contested flor ignores the number of flors held

**Engine.** `_flor_action` `FLOR_PASS` → `_resolve_flor(state, state.flor_stake)` pays one flat
`pts` (3 for la mía flor, 5 for con flor envido) to the winning team (`game.py:273-277`, `:297-307`,
`:285`). The one-sided branch correctly pays `3 * len(members)` (`:180`).

**Spec.** Each flor is worth 3 and the winner collects the flors of its own teammates too: S2 Art 20:
«Los puntos de las flores de los compañeros de equipo del ganador se sumarán a los de éste»; Art
31 for «con flor». Con flor envido = envido amount + flor(s), not a fixed 5 (S1 Art 23).

**Repro (observed).** Flor seats `[0, 4, 5]` with scores `[35, 0, 0, 0, 38, 28]` (team A holds two
flors, team B one; A's best, 38, wins): `FLOR_CHICO` + `FLOR_PASS` → `hand_pts == [3, 0]`; the
spec gives A 6.

**Frequency.** ≥2 flors on a side in 7 773 of 30 523 contested flors (25 %; 3.9 % of deals).

### A-09 — `FOLD` against a plain flor announcement

**Engine.** `game.py:249-251`: the answering side always gets `[FOLD, FLOR_PASS, …]`; after
`FLOR_CHICO` that includes `FOLD`, which pays the bidder `flor_prev_stake` (3).

**Spec.** A plain flor is not a challenge: it is settled by comparing flor values (S1 Art 14; S2
Art 20; S4: the answer to a flor is «Flor»). Declining applies to the *challenges* con flor envido
/ contra flor al resto (S1 Art 24; S4).

**Repro (observed).** Responder holds the better flor; bidder plays `FLOR_CHICO`; responder
`FOLD` → `hand_pts == [3, 0]` for the weaker bidder.

**Impact.** The action is dominated for the stronger flor (loses 3 instead of winning 3) and
equivalent to `FLOR_PASS` for the weaker one. Cosmetic for rational agents; adds a bad action for
exploration.

### A-10 — «Con flor» ladder missing calls (variant-dependent)

The flor ladder offers `FLOR_CHICO`, `FLOR_CON_ENVIDO` (5), `FLOR_CONTRA_RESTO`. S1/S2/S5 apply the
whole envido ladder «con flor» (S5 names «Con flor envido» and «Con flor envido la falta»; S2 Art
37 chains «con flor la falta envido» → «contra flor el resto»); S3 lists exactly three calls.
Against S3 this is a match; against S1/S2/S5 a legal action is missing. See
[V-02](rules.md#10-variants-register).

### A-11 — No «irse al mazo» / «pasar» during card play

`legal_actions` in `Phase.PLAY` returns only the cards in hand (`game.py:127-128`). Going to the
mazo is a core action (S1 Art 50; S2 Art 88–90; S3 glossary «irse al mazo»). In the engine it exists
only as `FOLD` during a pending bid. Not mentioned in the module docstring.

### A-12 to A-15 — Documented and variant simplifications

- **A-12 Truco only before play.** Documented at `game.py:8` («Truco bidding happens as a dedicated
  phase before card play (not interleaved)»). The truco can be called at any point of the hand (S3
  L89: «En cualquier momento de la mano, un jugador en su turno puede decir truco»; S2 Art 49–50), and
  the side that said «quiero» may retruco in later tricks (S3 L91). After `TRUCO_PASS` the engine
  goes straight to play (`:485-487`) and no raise is possible.
- **A-13 Two-player bidding model.** Documented at `game.py:5-7`. Teammates cannot raise on behalf
  of the side (S2 Art 21–22 let any member call; Art 50 any member truco).
- **A-14 No pico a pico / malas-buenas / chicos.** Documented at `game.py:9`. Single game to
  `target` (default 40) = S3's total; S2 plays three chicos of 40; S1 plays chicos of 20
  ([V-04](rules.md#10-variants-register)). Falta/resto limits in pico a pico differ between sources
  ([V-03](rules.md#10-variants-register)).
- **A-15 Not implemented, not documented:** echar los perros / a ley de juego (S2 Art 70–82; S4),
  real-envido multiplier and «hasta igualar envido» (S2 Art 24), simultaneous envido + truco (S2 Art
  69).

### A-16 — Documentation / comment errors (cosmetic)

- `game.py:11`: «Contra flor al resto pays `target - winner's current score`» — the code uses the
  bidder's score (A-02).
- `game.py:305`: «Tie: no pts awarded» followed by `:307` awarding team A (A-06).
- `game.py:244`: `if True:` — dead conditional around `FLOR_CON_ENVIDO`.
- `game.py:258-259`: the same-team branch of `_flor_legal` is unreachable in the 2-player flor model.

---

## Appendix A — Reproduction scripts

All read-only: they `import engine` from the main checkout (`uv run --no-sync python …`), mutate only
in-memory `GameState`s, and use a **fresh `TrucoGame()` per scenario** (see Appendix B). The helper
below is shared; each scenario is the snippet shown next to its finding.

```python
from engine.actions import Action
from engine.game import TrucoGame
from engine.game_state import TEAM_A, TEAM_B, team_of
from engine.phases import Phase

def first_seed(pred, **kw):               # deterministic: fresh game per seed
    return next(s for s in range(200_000) if pred(TrucoGame().reset(seed=s, **kw)))

# A-03: VALE_CUATRO over TRUCO
s = first_seed(lambda st: st.phase == Phase.ENVIDO, scores=[38, 30])
g = TrucoGame(); st = g.reset(seed=s)
while st.phase == Phase.ENVIDO:
    g.apply_action(st, Action.ENVIDO_PASS)
g.apply_action(st, Action.TRUCO)
print([a.name for a in g.legal_actions(st)])   # includes VALE_CUATRO
```

Spec check (hierarchy, envido/flor points, hand winner): an independent implementation of S1 Art
8–10 and Art 41 written from the source tables, compared with `card_strength`, `tiene_flor`,
`calcular_envido`, `calcular_flor`, and `_check_early_winner` / `_compute_hand_winner`, over every
muestra and card pair, 300 000 random hands (seed 99), and the 27 trick sequences.

Frequencies: `engine.truco.simular_mano` over 200 000 deals (seed 12345). Ties: for no-flor deals
simulate S2 Art 39 with the `envido` figures (mano declares, then repeatedly the first rival of the last
declarer whose figure is strictly higher; winner = side of the last declarer; reading (a) orders rivals
rightward from the declarer, reading (b) from mano) and compare with the engine's `max_A >= max_B`;
for contested flors do the same with `flor_score` restricted to flor holders. Trick sequences: 20 000
hands of uniform-random card play with every bidding phase answered by its `…_PASS` action.

## Appendix B — Seeds are not reproducible on a reused game (not a rules item)

`TrucoGame.__init__` builds the deck once (`game.py:51`), and `reset` shuffles it **in place**
(`game.py:60` → `truco.py:155` `rng.shuffle(mazo)`), so the deal for a given seed depends on every
earlier `reset` on that instance.

```
same game, same seed, equal deals: False
fresh games, same seed, equal deals: True
```

`scripts/benchmark.py:236` creates one `TrucoGame()` and reuses it, with `reset(seed=…)` at `:93` and
`:121`. A whole run in one process and a fixed order is presumably still repeatable, but a single
hand cannot be replayed from its per-hand seed. This is a reproducibility issue for any experiment
that stamps seeds (e.g. 008), not a game-rules discrepancy, so no rules issue was filed for it.
