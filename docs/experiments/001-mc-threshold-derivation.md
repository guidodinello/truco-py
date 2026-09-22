# MC envido/flor threshold derivation

**Date:** 2026-03-15 / 2026-03-16 (per file mtimes in `results/`; predates this
repo's git history — see `docs/experiments/README.md` caveat 5)
**Note:** [gamekit#005 — Eval statistics: Wilson intervals and eval-in-loop](https://github.com/guidodinello/gamekit/blob/main/docs/research/005-eval-statistics.md)

## Config

Monte Carlo simulations run via `main.py --experimento <nombre> --n <N> --seed 42`
(see `README.md`'s "Agregar un experimento nuevo" section). Experiments:
`flor` (P(≥2 same-team flor)), `envido` (opponent-envido conditional
probabilities), `envido_1v1`, `envido_equipo`, `flor_decision`,
`flor_decision_1v1`. All at `--seed 42`.

## Environment

No commit — run predates `e70dd16` (this repo's initial commit, 2026-06-04).
Pre-gamekit: intervals were computed with a clamped Wald approximation
(`z = 1.96`), not Wilson — `gamekit` adoption happened later, in truco-py#1.

## Result

Flor, P(≥2 same team with flor), `results/n10000000_seed42.txt:5-8` (n=10,000,000):
**11.7127%, IC 95% [11.6927%, 11.7326%]**, SE 0.0102%.

The same experiment at n=1,000,000, `results/n1000000_seed42.txt:5-8`: 11.7509%,
[11.6878%, 11.8140%], SE 0.0322%.

**`README.md:236` mislabels these.** Its row reads:

> P(≥2 del mismo equipo con flor) | ~11.75% (IC 95%: [11.69%, 11.81%]) | 10 000 000

The percentage and interval (~11.75%, [11.69%, 11.81%]) are the **n=1,000,000**
file's numbers, not the n=10,000,000 file's (11.7127%, [11.6927%, 11.7326%]).
The `n` column says 10,000,000; the figures next to it are from the 1,000,000 run.

Envido conditional probabilities, `results/envido_n1000000_seed42.txt`
(n=1,000,000, matches `README.md:242-243` exactly):
- P(some opponent >20 pts | I have 30) ≈ 98.09%, [97.98%, 98.20%]
- P(some opponent >30 pts | I have 30) ≈ 66.0%, [65.60%, 66.38%]

Envido threshold to bid, 1v1, `results/envido_1v1_n1000000_seed42.txt:23-26`:
27→46.4% [46.1%,46.8%], **28→54.2% [53.7%,54.6%]** (crosses 1/2), 29→59.1%,
30→65.7%. This is the source of `README.md`'s "umbral mínimo 28 puntos" table
and of `ThresholdAgent`'s 1v1 envido threshold.

Envido threshold to bid, as pie (team), `results/envido_equipo_n1000000_seed42.txt`
(n=1,000,000): 32→40.7% [40.4%,41.1%], **33→51.3% [51.0%,51.6%]** (crosses 1/2),
34→66.0% [65.7%,66.2%], 35→82.7%, 36→93.1%, 37→100.0%. This matches
`README.md:269-273`'s table exactly. **`README.md:278` cites the source as
`results/envido_equipo_n5000000_seed42.txt` — that file does not exist.** Only
`envido_equipo_n500000_seed42.txt` and `envido_equipo_n1000000_seed42.txt` are on
disk, and the table's numbers match the n=1,000,000 file, not a 5,000,000 run.

Flor decision, 1-vs-2 (I alone have flor), `results/flor_decision_n1000000_seed42.txt`
(n=1,000,000 hands, 5,774 filtered): 36→44.4% [39.5%,49.3%], **37→59.7%
[54.6%,64.7%]** (crosses 1/2), **38→64.8% [59.3%,70.2%]** (crosses 2/3). Matches
`README.md:284-291`.

Flor decision, 1v1, `results/flor_decision_1v1_n1000000_seed42.txt`
(37,597 filtered): 34→46.1%, **35→55.4% [53.5%,57.3%]** (crosses 1/2), 36→64.6%.
Matches `README.md:309-313`.

## Verdict

**gamekit#005 (Wilson intervals / eval-in-loop):** does not test this note's
hypothesis. These MC simulations already used a confidence-interval method (Wald,
pre-gamekit; Wilson after truco-py#1) and were run to completion rather than
watched in-loop for early collapse — the note's actual concern (catching a
degenerate run before the budget is spent) doesn't apply to a fixed-`n` batch
simulation. Linked here as the nearest existing note because gamekit has no
"threshold-derivation via Monte Carlo" note; recorded for the numbers, which are
the best-evidenced work in this repo (real `n` up to 1e7, fixed seed, CIs already
computed at the source).

Two data-hygiene issues found while fact-checking (not fixed in this PR, see the
main PR description): `README.md:236`'s flor row mislabels an n=1,000,000 result
as n=10,000,000, and `README.md:278` cites a `results/*.txt` file that does not
exist on disk.
