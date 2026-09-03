"""Tier-2 deep model #1: an LSTM sequence autoencoder for trend-level
anomaly detection.

Trained only on healthy telemetry windows (unsupervised), it learns to
reconstruct normal multivariate sensor trajectories (voltage, current,
temperature, vibration, frequency, load). A degrading asset produces a
trajectory the model was never trained to reconstruct, so the
reconstruction error itself becomes the anomaly score -- no fault labels
are required to train it, which matters because real fleets have very few
labelled failures.
"""

from __future__ import annotations

import torch
from torch import nn


class LSTMAutoencoder(nn.Module):
    """Sequence-to-sequence LSTM autoencoder.

    Input:  (batch, seq_len, n_features)
    Output: reconstruction of the same shape.
    """

    def __init__(
        self,
        n_features: int = 6,
        hidden_size: int = 32,
        latent_size: int = 12,
        num_layers: int = 1,
    ):
        super().__init__()
        self.n_features = n_features
        self.hidden_size = hidden_size
        self.latent_size = latent_size

        self.encoder_rnn = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.to_latent = nn.Linear(hidden_size, latent_size)
        self.from_latent = nn.Linear(latent_size, hidden_size)
        self.decoder_rnn = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.output_layer = nn.Linear(hidden_size, n_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, seq_len, _ = x.shape

        _, (h_n, _) = self.encoder_rnn(x)
        latent = self.to_latent(h_n[-1])  # (batch, latent_size)

        # Repeat the latent code across time as the decoder's driving input
        # -- a standard, simple seq2seq-autoencoder recipe that keeps the
        # model small enough to run comfortably on edge-adjacent hardware.
        decoder_input = self.from_latent(latent).unsqueeze(1).repeat(1, seq_len, 1)
        decoded, _ = self.decoder_rnn(decoder_input)
        reconstruction = self.output_layer(decoded)
        return reconstruction

    @torch.no_grad()
    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """Per-sample mean squared reconstruction error, shape (batch,)."""
        self.eval()
        recon = self.forward(x)
        return torch.mean((recon - x) ** 2, dim=(1, 2))
