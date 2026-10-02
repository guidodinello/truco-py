"""Behavioral cloning (exp 009): held-out validation by game, full-actor + value training."""

import numpy as np
import pytest
import torch

from engine.actions import N_ACTIONS
from scripts.pretrain_bc import VAL_EVERY, collect_dataset, split_by_game, train_bc
from tests.helpers import tiny_model


@pytest.fixture(scope="module")
def ds():
    return collect_dataset(40, seed=5, workers=1)


def test_split_is_by_game_and_disjoint(ds):
    val = split_by_game(ds["game_ids"])
    train_games, val_games = set(ds["game_ids"][~val]), set(ds["game_ids"][val])
    assert val_games and train_games
    assert not train_games & val_games, "a game's decisions must not straddle train and val"
    assert val_games == {g for g in range(40) if g % VAL_EVERY == 0}


def test_dataset_shapes_and_value_targets(ds):
    n = len(ds["actions"])
    assert ds["obs"].shape == (n, 204) and ds["obs"].dtype == np.float32
    assert ds["masks"].shape == (n, N_ACTIONS)
    assert ds["masks"][np.arange(n), ds["actions"]].all(), "the teacher only plays legal actions"
    assert np.isfinite(ds["values"]).all() and np.abs(ds["values"]).max() <= 1.0


def test_collection_is_independent_of_worker_count(ds):
    two = collect_dataset(40, seed=5, workers=2)
    a, b = np.argsort(ds["game_ids"], kind="stable"), np.argsort(two["game_ids"], kind="stable")
    for key in ("obs", "actions", "values", "game_ids"):
        assert np.array_equal(ds[key][a], two[key][b]), key


def test_context_bank_changes_the_games(tmp_path):
    from training.context_bank import build_bank

    bank = build_bank(4, seed=1)
    bank.save(tmp_path / "b.npz")
    with_bank = collect_dataset(20, seed=5, bank_path=tmp_path / "b.npz")
    without = collect_dataset(20, seed=5)
    assert with_bank["obs"].shape[1] == without["obs"].shape[1]
    assert not np.array_equal(with_bank["obs"][:50], without["obs"][:50])


def test_train_bc_updates_the_whole_actor_and_reports_validation(ds):
    model = tiny_model(seed=3)
    before = {k: v.clone() for k, v in model.policy.state_dict().items()}
    history = train_bc(ds, model, epochs=2, batch_size=256, lr=1e-3)

    assert [h["epoch"] for h in history] == [1, 2]
    for h in history:
        assert {"train_acc", "val_acc", "val_loss", "val_vf_loss"} <= set(h)
        assert 0.0 <= h["val_acc"] <= 1.0
    after = model.policy.state_dict()
    changed = {k for k in before if not torch.equal(before[k], after[k])}
    # exp 002 trained action_net only, on frozen random features; 009 trains everything
    assert any(k.startswith("mlp_extractor.policy_net") for k in changed)
    assert any(k.startswith("action_net") for k in changed)
    assert any(
        k.startswith("value_net") or k.startswith("mlp_extractor.value_net") for k in changed
    )
    assert history[-1]["val_loss"] < 4.2  # below ln(65): it learned something on held-out games
