"""Small causal sequence models for supervised battery prognosis."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class CausalBlock(nn.Module):
    def __init__(self, width: int, dilation: int) -> None:
        super().__init__()
        self.padding = 2 * dilation
        self.conv = nn.Conv1d(width, width, 3, dilation=dilation)
        self.norm = nn.LayerNorm(width)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Left padding prevents convolution from inspecting future positions.
        convolved = self.conv(F.pad(x, (self.padding, 0)))
        normalized = self.norm(convolved.transpose(1, 2)).transpose(1, 2)
        return x + F.gelu(normalized)


class BatteryTCN(nn.Module):
    def __init__(self, n_features: int = 4, width: int = 16) -> None:
        super().__init__()
        self.input = nn.Conv1d(n_features, width, 1)
        self.blocks = nn.Sequential(
            CausalBlock(width, 1), CausalBlock(width, 2), CausalBlock(width, 4)
        )
        self.output = nn.Linear(width, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        hidden = self.blocks(self.input(x.transpose(1, 2)))
        return F.softplus(self.output(hidden[:, :, -1])).squeeze(-1)


class BatteryGRU(nn.Module):
    def __init__(self, n_features: int = 4, width: int = 16) -> None:
        super().__init__()
        self.gru = nn.GRU(n_features, width, batch_first=True)
        self.output = nn.Linear(width, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, hidden = self.gru(x)
        return F.softplus(self.output(hidden[-1])).squeeze(-1)
