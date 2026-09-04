"""Tier-2 deep model #2: a GRU regressor estimating Remaining Useful Life
(RUL) directly from a window of multivariate telemetry.

Where the autoencoder answers "is something wrong?", this model answers
"how long until it fails?" -- trained on the simulator's labelled
degradation trajectories (see ``argus.simulator``), it turns raw sensor
trends into an operationally useful number: hours (or run-steps) of
remaining service life, which is what actually drives a maintenance
decision on a ship or a UAV squadron.
"""

from __future__ import annotations

import torch
from torch import nn


class RULRegressorGRU(nn.Module):
    """GRU encoder + MLP head predicting normalized remaining useful life
    (RUL) in [0, 1], where 0 == failure is imminent and 1 == full healthy
    horizon remaining.

    Input:  (batch, seq_len, n_features)
    Output: (batch,) normalized RUL estimate.
    """

    def __init__(
        self,
        n_features: int = 6,
        hidden_size: int = 32,
        num_layers: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.gru = nn.GRU(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1),
            nn.Sigmoid(),  # keeps the RUL estimate bounded in [0, 1]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, h_n = self.gru(x)
        last_hidden = h_n[-1]  # (batch, hidden_size)
        return self.head(last_hidden).squeeze(-1)
