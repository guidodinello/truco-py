"""The inference server must serve real models or fail loudly -- never guess (exp 005)."""

import numpy as np
import pytest

from engine.actions import N_ACTIONS
from tests.helpers import save_old_checkpoint, tiny_model
from training.inference_server import InferenceServer


@pytest.fixture
def server():
    s = InferenceServer(n_envs=1, device="cpu")
    yield s
    s.stop()


def _request(server: InferenceServer, path: str, legal: list[int]) -> int:
    mask = np.zeros(N_ACTIONS, dtype=bool)
    mask[legal] = True
    return server.make_handle(0).request(path, np.zeros(204, np.float32), mask)


def test_unknown_model_raises_instead_of_returning_the_first_legal_action(server):
    with pytest.raises(RuntimeError, match="no model for /nope.zip"):
        _request(server, "/nope.zip", [7, 8])


def test_registered_model_answers_with_a_legal_action(server, tmp_path):
    path = tmp_path / "m.zip"
    tiny_model().save(str(path))
    server.update_model(str(path))
    for legal in ([7, 8, 30], [2], [40, 41, 42]):
        assert _request(server, str(path), legal) in legal


def test_snapshot_is_served_under_its_final_name_before_the_rename(server, tmp_path):
    tmp, final = tmp_path / ".tmp_5.zip", tmp_path / "snap_0000000005.zip"
    tiny_model().save(str(tmp))
    server.update_model(str(tmp), key=str(final))  # registered while it still has the tmp name
    assert _request(server, str(final), [3, 4]) in (3, 4)
    with pytest.raises(RuntimeError):
        _request(server, str(tmp), [3, 4])


def test_a_53_action_checkpoint_is_refused(server, tmp_path):
    old = save_old_checkpoint(tmp_path / "old.zip")
    with pytest.raises(ValueError, match="53 actions"):
        server.update_model(str(old))
