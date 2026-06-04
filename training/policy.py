"""
Custom MaskableActorCriticPolicy with auxiliary prediction heads.

TrucoActorCriticPolicy extends the standard policy with two small heads
trained to predict MC-known win probabilities from the shared actor trunk:

  envido_head — P(my envido wins 1v1)   supervised by ENVIDO_WIN_PROB table
  flor_head   — P(my flor wins 1v1)     supervised by FLOR_WIN_PROB table

Labels are derived from obs[133] (envido score) and obs[134] (flor score),
which are already encoded in every observation. No changes to rollout
collection are needed — labels are computed from the buffer at training time.

The aux heads sit on top of latent_pi (actor branch). This forces the shared
trunk to learn representations that encode sub-game win probability, which
generalises to the full bidding decisions.
"""

import torch as th
import torch.nn as nn
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy


class TrucoActorCriticPolicy(MaskableActorCriticPolicy):
    """MaskableActorCriticPolicy + envido/flor auxiliary prediction heads."""

    def _build(self, lr_schedule) -> None:
        super()._build(lr_schedule)
        latent_dim = self.mlp_extractor.latent_dim_pi  # 256 with net_arch=[256,256]
        self.envido_head = nn.Linear(latent_dim, 1)
        self.flor_head = nn.Linear(latent_dim, 1)
        # Small init: heads start near 0.5 output (sigmoid(0)=0.5) and don't
        # disturb the trunk gradient norms during early training.
        nn.init.normal_(self.envido_head.weight, std=0.01)
        nn.init.zeros_(self.envido_head.bias)
        nn.init.normal_(self.flor_head.weight, std=0.01)
        nn.init.zeros_(self.flor_head.bias)

    def predict_aux(self, obs: th.Tensor) -> tuple[th.Tensor, th.Tensor]:
        """
        Forward pass through the shared trunk and auxiliary heads.

        Parameters
        ----------
        obs : th.Tensor, shape (N, OBS_DIM)

        Returns
        -------
        envido_pred : th.Tensor, shape (N, 1), values in (0, 1)
        flor_pred   : th.Tensor, shape (N, 1), values in (0, 1)
        """
        features = self.extract_features(obs, self.features_extractor)
        if self.share_features_extractor:
            latent_pi, _ = self.mlp_extractor(features)
        else:
            pi_features, _ = features
            latent_pi = self.mlp_extractor.forward_actor(pi_features)

        return (
            th.sigmoid(self.envido_head(latent_pi)),
            th.sigmoid(self.flor_head(latent_pi)),
        )
