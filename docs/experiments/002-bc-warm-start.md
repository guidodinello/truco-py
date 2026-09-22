# BC pre-training warm start

**Date:** 2026-04-05 (`logs/bc_pretrain.log` mtime)
**Note:** [gamekit#002 — Behavior-cloning warm start before PPO](https://github.com/guidodinello/gamekit/blob/main/docs/research/002-bc-warm-start.md)

## Config

`uv run scripts/pretrain_bc.py` — from `logs/bc_pretrain.log:2-6`: 50,000 games
collected, 10 epochs, batch size 2048, fresh model (no `--load`), 256x256
network, device cuda. `scripts/pretrain_bc.py:111-135` is the training loop:
`Adam` optimizer over `policy.action_net`, cross-entropy loss against
`ThresholdAgent`'s recorded actions, masked to legal actions.

## Environment

No commit — run predates `e70dd16` (this repo's initial commit, 2026-06-04).

## Result

`logs/bc_pretrain.log:19-28`, verbatim:

```
[1/3] Collecting trajectories...
  collected 50,000/50,000 games (650,312 steps)
  Done: 650,312 (obs, action) pairs

[3/3] Training...
  BC training: 650,312 samples, 10 epochs, batch=2048
  epoch  1/10  loss=0.4621  acc=0.821
  ...
  epoch 10/10  loss=0.1999  acc=0.920

Done in 1050.1s. Saved to checkpoints/bc_init.zip
```

Final accuracy: **92.0%**. Wall time: **1050.1s ≈ 17.5 min**.

**This is training-set accuracy, not held-out accuracy.**
`scripts/pretrain_bc.py:132-135` builds a single `TensorDataset` from the whole
650,312-pair collection and a single `DataLoader` over it — no train/test split
exists anywhere in the file. Inside the epoch loop (`:146-166`), the same
`obs_b, act_b, mask_b` batches that `optimizer.step()` (`:161`) trains on are the
ones `correct += (logits.argmax(dim=1) == act_b).sum()` (`:164`) scores against,
and `accuracy = correct / n_samples` (`:167`) reports that as `acc`. The reported
92.0% is measured on exactly the data the model was just updated on.

This contradicts the stated goal in `docs/plan_rl_agent.md:275`:
> Goal: BC accuracy ≥ 70% on held-out ThresholdAgent actions

No held-out accuracy was ever measured, and no cold-start-vs-BC-init ablation
exists in this repo — there is no benchmark comparing a PPO run started from
`bc_init.zip` against one started from random weights.

`README.md:117` propagates the unqualified figure ("~92% accuracy") without the
training-set caveat. `README.md:126`/`:158` estimate the BC step at "~5 min"; the
measured wall time was 17.5 min — off by roughly 3.5×.

## Verdict

**gamekit#002:** inconclusive. The measured 92.0% cannot support the
hypothesis that BC warm-start reaches a better starting point than cold-start,
for two independent reasons: (1) it is training-set accuracy against a spec that
required held-out accuracy, so even the accuracy number itself is not evidence of
generalization; (2) no cold-start comparison run exists to test the warm-start
claim directly. This matches gamekit#002's own stated reasoning for staying at
status `planned` rather than `validated`.
