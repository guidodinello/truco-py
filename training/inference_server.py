"""
Centralized GPU inference server for checkpoint opponents.

In selfplay mode each subprocess runs up to 5 opponent agents, some of which
are checkpoint-based (loaded MaskablePPO models).  Running these on CPU inside
16 forked workers is slow (~2ms per call × ~2.5 avg calls/step × 16 envs).

This module moves that inference to a daemon thread in the main process which
has unrestricted GPU access.  Each subprocess holds a ``Connection`` end of a
duplex ``multiprocessing.Pipe``.  When a checkpoint agent needs an action it
pickles (path, obs, mask) onto the pipe.  The daemon thread collects all
ready pipes with ``connection.wait()``, groups requests by checkpoint path,
runs one GPU ``predict()`` per distinct model, and sends action ints back.

Bandwidth estimate:
  request  ≈ 60 + 816 + 53 = ~930 bytes (path str + float32[204] + bool[53])
  response ≈ 4 bytes (int)
  at 1 250 requests/s (16 envs × 500 fps × 0.5 threshold_mix × 2.5 avg opp turns):
  ~1.2 MB/s on the pipe — well within OS pipe throughput.
"""

import threading
from collections import defaultdict
from dataclasses import dataclass
from multiprocessing.connection import Connection, wait
from typing import cast

import numpy as np

from log import get_logger

logger = get_logger(__name__)


@dataclass
class InferenceHandle:
    """Picklable proxy held by each subprocess env.

    The subprocess calls ``request()`` to send (path, obs, mask) to the
    inference server and block until it receives the action int back.
    """

    conn: Connection

    def request(self, path: str, obs: np.ndarray, mask: np.ndarray) -> int:
        self.conn.send((path, obs, mask))
        return self.conn.recv()


class InferenceServer:
    """GPU inference server for checkpoint opponents.

    Holds a dict of MaskablePPO models (one per checkpoint path) on GPU.
    A daemon thread collects requests from all env subprocesses, groups them
    by checkpoint path, and runs one GPU ``predict()`` per distinct model per
    batch.

    Typical usage in the main process::

        server = InferenceServer(n_envs=16, device="cuda")
        # pass server.make_handle(i) to each env subprocess's TrucoEnv

        # called by CheckpointCallback after each model.save():
        server.update_model(path_to_new_checkpoint)

        server.stop()   # signal shutdown (optional — daemon thread dies with process)
    """

    _BATCH_WAIT_S: float = 0.005  # seconds to collect a batch before processing

    def __init__(self, n_envs: int, device: str = "cuda") -> None:
        self._n_envs = n_envs
        self._device = device
        self._models: dict[str, object] = {}  # path → MaskablePPO
        self._lock = threading.Lock()
        self._stop = threading.Event()

        # One duplex pipe per env: server-side conn is held here;
        # client-side conn is sent to the subprocess via make_handle().
        self._server_conns: list[Connection] = []
        self._client_conns: list[Connection] = []
        for _ in range(n_envs):
            from multiprocessing import Pipe

            sc, cc = Pipe(duplex=True)
            self._server_conns.append(sc)
            self._client_conns.append(cc)

        self._thread = threading.Thread(
            target=self._serve, daemon=True, name="inference-server"
        )
        self._thread.start()
        logger.info("InferenceServer started  device=%s  n_envs=%d", device, n_envs)

    # ── Public API (main-process thread) ─────────────────────────────────────

    def make_handle(self, env_id: int) -> InferenceHandle:
        """Return the picklable client-side handle for subprocess env *env_id*."""
        return InferenceHandle(conn=self._client_conns[env_id])

    def update_model(self, path: str) -> None:
        """Load a new checkpoint onto the server GPU.

        The 13-second load happens *outside* the lock so the inference thread
        keeps serving existing models while the new one loads.  The dict entry
        is swapped atomically under the lock.
        """
        from sb3_contrib import MaskablePPO

        logger.info("InferenceServer: loading %s → %s", path.split("/")[-1], self._device)
        new_model = MaskablePPO.load(path, device=self._device)
        with self._lock:
            self._models[path] = new_model
        logger.info("InferenceServer: model ready  pool_size=%d", len(self._models))

    def stop(self) -> None:
        """Signal the server thread to shut down cleanly."""
        self._stop.set()

    # ── Background thread ─────────────────────────────────────────────────────

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                ready = cast(
                    list[Connection],
                    wait(self._server_conns, timeout=self._BATCH_WAIT_S),
                )
                if not ready:
                    continue

                batch: list[tuple[Connection, str, np.ndarray, np.ndarray]] = []
                for conn in ready:
                    try:
                        path, obs, mask = conn.recv()
                        batch.append((conn, path, obs, mask))
                    except (EOFError, OSError):
                        pass  # subprocess exited — skip

                self._process_batch(batch)

            except Exception:
                logger.exception("InferenceServer: unexpected error in serve loop")

    def _process_batch(
        self, batch: list[tuple[Connection, str, np.ndarray, np.ndarray]]
    ) -> None:
        if not batch:
            return

        groups: dict[str, list] = defaultdict(list)
        for item in batch:
            _, path, _, _ = item
            groups[path].append(item)

        for path, items in groups.items():
            with self._lock:
                model = self._models.get(path)

            try:
                if model is None:
                    # Model not loaded yet — return a random legal action.
                    for conn, _, _, mask in items:
                        legal = np.where(mask)[0]
                        conn.send(int(legal[0]) if len(legal) else 0)
                    continue

                obs_arr = np.stack([b[2] for b in items])
                mask_arr = np.stack([b[3] for b in items])
                actions, _ = model.predict(  # type: ignore[union-attr]
                    obs_arr, action_masks=mask_arr, deterministic=False
                )
                for i, (conn, _, _, _) in enumerate(items):
                    conn.send(int(actions[i]))

            except Exception:
                logger.exception(
                    "InferenceServer: error on batch for %s — sending fallback actions",
                    path.split("/")[-1],
                )
                for conn, _, _, mask in items:
                    try:
                        legal = np.where(mask)[0]
                        conn.send(int(legal[0]) if len(legal) else 0)
                    except Exception:
                        pass
