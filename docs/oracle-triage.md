# pytruco oracle — triage report

Issue [#89](https://github.com/guidodinello/truco-py/issues/89). We run the same inputs through
our engine and [pytruco](https://github.com/truquito/pytruco) 0.1.3 (MIT, pure Python, no
dependencies; pinned, dev-only, never imported from `engine/`) and treat each disagreement as a
lead. **Nothing here is decided and nothing in `engine/` or `docs/rules.md` was changed**: every
entry is a guess for you to confirm per diff. A confirmed "bug ours" gets a fix + regression test;
a "variant" goes into `docs/rules.md` §10 with sources.

Code: `tests/oracle/` (adapter, comparisons, driver, registry of known diffs), tests
`tests/test_oracle_pure.py` (layer 1, default run, ~4 s) and `tests/test_oracle_hands.py` (layer 2,
`pytest -m slow`, ~20 s for 20,000 hands). Each test fails on an unexplained diff **and** on a
registry entry that no longer occurs, so a fix on either side shows up.

## What agrees

Layer 1 compared every case below and found **no diff**:

- `es_pieza`: 40 cards × 40 muestras.
- Card strength order (sign of `a − b`; the scales differ, ours 0–18 vs theirs 10–34): every ordered
  pair of non-muestra cards × 40 muestras. This includes the equal-strength = parda behaviour (V-07).
- Flor detection: every 3-card hand × muestra (39 cards to choose from, so 365,560 hands).
- Envido (hands where neither engine sees a flor): same 365,560 hands.

## Diffs found

"Ours" / "theirs" = our engine / pytruco. Minimal case = the shortest one the random search found
(seed in the test's seed range; `prefix` is our action sequence; seats `s0..s5`, even seats are
team 0).

| ID | Layer | What differs | Minimal case | Guess |
|---|---|---|---|---|
| D-01 | 1 | **Flor derecha without a pieza.** We add 20, pytruco returns the bare sum. | muestra 1 de Espadas, hand 3, 6, 7 de Espadas: ours 36, theirs 16 (14,560 hands) | **bug theirs.** rules.md §4.1: range 20–47 (S3 L134; S4). Their own range would be 0–18 and a flor could never beat an envido-sized figure; their tests only cover a 3-pieza flor. |
| D-02 | 1 | **Falta / resto while the leader is in malas.** Theirs: half the chico minus the *winner's* score. Ours: chico minus the *leader's* score. | scores 0–0: ours 40, theirs 20; scores 19–19: ours 21, theirs 1 (800 score/winner pairs, all with both sides < 20) | **ours is right (pytruco variant).** S2 Art 23: one may envidar up to «los puntos que resten al jugador o equipo que lleve ventaja para completar la cantidad fijada para el chico»; Art 25 defines the falta as that amount. Half the chico is not in S2. Also S3 L109. *(Second read, original S2 text.)* |
| D-03 | 2 | **Falta envido after earlier envites.** Theirs pays the falta *plus* the tantos accumulated before it; ours pays the falta alone. | `s4:REAL_ENVIDO s5:FALTA_ENVIDO s0:QUIERO` (seed 80): ours 14, theirs 17 | **bug theirs.** S2 Art 23 caps any envido at what the leader still needs to complete the chico, so falta + earlier tantos (17 vs a falta of 14) exceeds it. Art 25 says accepted envites «modifican la falta» by their amounts, which could matter when the winner is not the leader; ours equals the falta in the common case. *(Second read.)* |
| D-04 | 2 | **«No quiero» to a raise of envido.** Theirs: accepted tantos + 1. Ours: accepted tantos. | `s4:ENVIDO s5:REAL_ENVIDO s0:FOLD` (seed 107): ours 2, theirs 3 | **bug theirs.** S2 Art 35: «el reenvite no aceptado no genera ganancia de punto a favor del reenvidante»; rules.md §7: «E,Real,NQ → 2» (S3 L117–118; S4). The +1 only applies to a first call (Art 24). *(Second read.)* |
| D-05 | 2 | **Contested flor, nobody envites.** Theirs: the winner collects 3 per flor of *both* sides. Ours: 3 per flor on the winner's own side. | both sides pass: seed 26, one flor each: ours 3, theirs 6 | **bug theirs** for a plain contest (S2 Art 20; S5: the loser's flors are lost, not paid to the winner). Paying the rival's flors belongs to contra flor only (S2 Art 31, V-01). |
| D-06 | 2 | **Who leads after a parda.** We: mano (first in turn order). Theirs: the first of the *tied* players in throwing order. Every later move by the other player is then rejected as out of turn. | seed 172: trick 1 is tied by `s3` (3 de Oros) and `s0` (3 de Espadas); ours leads `s1` (mano), theirs `s3` | **bug theirs.** rules.md §6: S1 Art 39 «corresponderá jugar en primer término la segunda carta al "mano"»; S2 Art 57. |
| D-07 | 2 | **Envido after a truco was accepted.** We allow it for a player who has not spoken (S1 Art 16 / S2 Art 22); pytruco rejects every envite once the truco is accepted. | `s0:TRUCO s1:QUIERO s0:card s1:card s2:ENVIDO` (seed 42) | **bug ours.** S2 Art 22 c) and **d)**: to envidar one must not have said «truco» or «quiero», and «que ningún integrante del equipo haya hecho lo mismo». We only check the individual player (`spoke_truco[p]`), so a teammate of the player who said truco could still envidar. pytruco's behaviour matches Art 22 d). *(Second read; was "bug theirs".)* |
| D-08 | 2 | **«El envido va primero» over a pending retruco / vale cuatro.** We allow it; pytruco only over a pending truco. | `s2:TRUCO s3:RETRUCO s4:FALTA_ENVIDO` (seed 853) | **bug ours, same root cause as D-07.** The answerer of a retruco is on the team that said «truco» (and a retruco counts as accepting the truco, Art 66), so Art 22 c)/d) bars their whole team from envidar. «El envido va primero» over a plain pending truco is unaffected. Note Art 60 itself does not state the rule (it only says envites are settled first, with Art 55), so our docstring citation is loose. *(Second read; was "unclear".)* |
| D-09 | 2 | **Tie between the two sides' best envido / flor.** We follow the declaration procedure (ties do not beat, so the side that declared the figure first wins). Pytruco gives the tie to the most-mano of the tied players. | `s5:FALTA_ENVIDO s0:QUIERO` (seed 8680): mano `s5` (31); `s1` (team 1) and `s4` (team 0) both hold 33; ours team 0 (declared first), theirs team 1 (`s1` is more mano) | **variant**, already documented: rules.md §3.5, V-14, audit A-05/A-06. Differs in ≈0.2 % of hands (452 of 183k). Note 1v1 is sourced «gana el mano» (S5), which both engines agree on. |
| D-10 | 2 | **Raising an envido after playing a card.** pytruco lets the answerer raise with 2 cards in hand; we require all 3 (S2 Art 35 → Art 22, 28). Counted only, not asserted: it shows as `theirs_only` in the driver stats (≈ 560 cases in 20,000 hands, all in the envido answer phase). | any envido called while the answerer already played trick 1 | **ours is right (pytruco is more permissive).** S2 Art 35: a reenvite needs every condition of Art 22, which includes b) «tener el envidante las tres cartas en su poder». Art 28 says the same for «con flor». *(Second read; was "unclear".)* |

Already in the variants register and whitelisted: **V-05** (real envido raised again over a real
envido: ours allows it, pytruco rejects it; 476 of 20,000 hands).

## What layer 2 deliberately leaves out

Each is a known structural difference, not a hidden failure:

- **Pico a pico** (V-12 / S2 Art 83–86): pytruco only has 2/4/6-player games; we only play 6-player
  hands, never the mano-a-mano alternation.
- **«A ley de juego»** (V-09): not in pytruco; our `Rules.ley_de_juego` stays off.
- **Envite calls with no pytruco equivalent** (V-10, V-02): dos/tres real envido, hasta igualar,
  the whole ladder played «con flor», contra flor al resto in the driver.
- **Full legal-action sets** are not compared: any rival may answer in pytruco, its mazo is
  per player and not turn-gated, flor must be sung explicitly, and the envite ladders have other
  shapes, so the sets differ at nearly every step. Instead we require that every action *we*
  allow is accepted by pytruco, and count what only pytruco allows (D-10).
- **Our MAZO** (the whole side concedes) is sent as one mazo per teammate, the current player
  last (otherwise pytruco closes the trick on the next teammate's mazo). A side where a player
  already threw all three cards cannot be translated (pytruco refuses mazo then), so that action
  is skipped.
- **Inputs that would only repeat a known diff are kept out:** deals with a contested flor that
  holds a flor derecha without a pieza (D-01) are skipped (~8 % of deals); starting scores are
  20–30 so the leader is out of malas (D-02).
- **Trick results** are compared only for tricks our engine resolved (pytruco also scores a trick
  left half-played by a fold or mazo).
- After an explained points diff the driver rebases and carries on; a hand where that pushes
  pytruco to the target while ours is not there stops silently (~1 % of hands).

## Second read against the original S2 text

D-02, D-03, D-04, D-07, D-08 and D-10 were re-read against the verbatim S2 rulebook (GranAventura,
2011 snapshot, see rules.md "Sources"; the fetch tool refuses web.archive.org, `curl` works and the
articles are marked `ARTICULO n`). The guesses above are the result. The quotes that decided them:

- **Art 22** (envidar válidamente): «a) Estar en juego. b) Tener el envidante las tres cartas en su
  poder. c) No haber dicho "truco" o "quiero" al truco o envido del adversario habilitado para
  poder hacerlo. d) Que ningún integrante del equipo haya hecho lo mismo. e) Usar la palabra
  "envido".»
- **Art 23**: «Se puede envidar válidamente hasta la cantidad de puntos o tantos que resten al
  jugador o equipo que lleve ventaja para completar la cantidad fijada para el chico en disputa».
- **Art 35**: «…reenvidar por los puntos porque fue envidado como mínimo o por más siempre se
  cumplan las condiciones establecidas en los incisos a), b), c), d) y e) del Artículo 22 … el
  reenvite no aceptado no genera ganancia de punto a favor del reenvidante».
- **Art 66**: «Tanto el "retruco" como el "vale cuatro" sin previo "quiero" de los desafíos
  respectivos de "truco" y "retruco" se tendrán por aceptación a éstos».

## Decision needed

All second-read verdicts above are mine; the remaining open ones:

- **D-07 / D-08: bug ours.** Fix: make the «truco / quiero» condition team-level (done in the
  follow-up PR, stacked on this one, which also drops both entries from the registry).
- **D-01, D-04, D-05, D-06 (bug theirs), D-02, D-03, D-10 (ours is right)**: nothing to change here;
  D-02 could go into rules.md §10 as a pytruco/gotruco variant if you want it recorded.
- **D-09** (tie by declaration procedure vs most-mano): a documented choice (§3.5, V-14), still yours
  to confirm.
