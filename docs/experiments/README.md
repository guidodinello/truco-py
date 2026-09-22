# Experiment logs

This folder is the truco-py half of a two-layer research convention adopted
across `gamekit` and its consumers (gamekit `docs/research/README.md`, commit
`1bb4298`):

> - **Technique notes live in `gamekit`.** One hypothesis per note, game-agnostic,
>   backed by a literature citation or an explicit "no external source; observed
>   in `<PR/run>`".
> - **Experiment logs live in the consumer repo**, under `docs/experiments/`. A log
>   holds the numbers: config, run id, and result. It links back to the note id
>   that it tests.
>
> A note's `Result` section links *forward* to the experiment log(s) that tested
> it; an experiment log links *back* to the note id that it tests. Neither repo
> owns both halves of the story, so the link is what keeps them traceable to
> each other.

Notes live at `gamekit/docs/research/NNN-slug.md` and are referenced from here as
`gamekit#NNN`. Logs in this folder are referenced as `log NNN`. The two id spaces
never collide because they're always written with a different prefix.

## How to add a log

1. Copy `gamekit/docs/research/EXPERIMENT-LOG-TEMPLATE.md` into this directory.
   gamekit's `NNN-slug` filename rule is a **note** convention and does not carry
   over to logs — the template and gamekit's README specify only the directory,
   not a filename shape. This repo additionally adopts `NNN-slug.md` locally, for
   a stable index — that's a truco-py choice, not something gamekit requires.
2. One log per run, or per closely related set of runs (e.g. a launch and the
   collapse that ended it are one log, not two).
3. Fill `Config`, `Environment`, `Result`, `Verdict` — every number cites the
   source file and line it came from. If a value isn't recorded anywhere, the log
   says `n not recorded in source` and computes no interval — never a
   back-filled guess.
4. A verdict (`validated` / `rejected` / `inconclusive`) is scored **per linked
   note**, not once per log. A log that links three notes writes three verdict
   lines. If the run doesn't actually test what a linked note claims, say so —
   "does not test this note's hypothesis; linked as nearest, recorded for the
   numbers" is a valid and expected verdict line.
5. Add a row to the index table below, sorted by id.

## Reading these logs — caveats that apply across all of them

These are stated once here instead of being repeated in every log:

1. **Seat-rotation confound (truco-py#1, see [log 006](006-seat-rotation-deconfound.md)).**
   Before 2026-09-20, `engine/game.py` always started `current_player=0` on Team A
   and Team A won ties — a permanent mano (first-to-act) advantage for one team.
   Every win rate dated before that PR was measured under this confound and is
   **not directly comparable** to anything measured after it.
2. **Checkpoint filename collision.** `truco_threshold_500000.zip` through
   `truco_threshold_3000000.zip` are from the 2026-06-05 run (shaped reward, no
   aux heads). `truco_threshold_3500000.zip` through `truco_threshold_5000000.zip`
   are from the 2026-04-12 run (aux heads on, MC rollouts, no shaping). **The file
   named `truco_threshold_2000000.zip` today is not the checkpoint that was
   benchmarked at 85.3%/84.0%** in the June session notes — that checkpoint was
   overwritten by the later run using the same step-count naming scheme.
3. **File mtime is not provenance.** `checkpoints/truco_threshold_final.zip`
   carries a September 2026 mtime because it was touched by a later PR's smoke
   test, even though it's an April 2026 training artifact. Dates in these logs
   come from session notes and log-file timestamps, never from `ls -l`.
4. **No benchmark output persists.** `scripts/benchmark.py` prints its result
   table to stdout and its logger has no file handler, so every RL win rate in
   the source material was hand-copied into a Markdown session note, not
   generated from a stamped JSON result. Where a note records a percentage but
   no `n`, or an `n` but no raw win/loss count, the corresponding log says so
   explicitly and computes no confidence interval.
5. **Most runs predate this repo's git history.** The repo's first commit is
   `e70dd16` (2026-06-04). Runs from April and early June have no commit to cite;
   their `Environment` sections say so rather than leaving the field blank.

## Index

| id | date | gamekit note(s) | verdict |
|---|---|---|---|
| [001](001-mc-threshold-derivation.md) | 2026-03-15/16 | gamekit#005 | does not test the note |
| [002](002-bc-warm-start.md) | 2026-04-05 | gamekit#002 | inconclusive |
| [003](003-threshold-training-plateau.md) | 2026-04-12 / 2026-06-05/06 | gamekit#009 | inconclusive |
| [004](004-april-selfplay-collapse.md) | 2026-04-05/06 | gamekit#001, gamekit#011 | inconclusive (#001) / supports (#011) |
| [005](005-june-threshold-mix-collapse.md) | 2026-06-06 | gamekit#001, gamekit#010, gamekit#011 | inconclusive (#001) / untested (#010) / supports (#011) |
| [006](006-seat-rotation-deconfound.md) | 2026-09-20 | gamekit#005 | inconclusive; no note covers this hypothesis |
| [007](007-gamekit-rl-adapter-parity.md) | 2026-09-20 | gamekit#005 | does not test the note (parity check, not a metrology test) |
