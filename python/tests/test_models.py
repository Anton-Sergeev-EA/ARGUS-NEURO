import torch

from argus.models import LSTMAutoencoder, RULRegressorGRU, SpectralBaselineDetector
import numpy as np


def test_autoencoder_forward_shape():
    model = LSTMAutoencoder(n_features=6, hidden_size=8, latent_size=4)
    x = torch.randn(5, 24, 6)
    out = model(x)
    assert out.shape == x.shape


def test_autoencoder_reconstruction_error_is_nonnegative():
    model = LSTMAutoencoder(n_features=6, hidden_size=8, latent_size=4)
    x = torch.randn(3, 24, 6)
    err = model.reconstruction_error(x)
    assert err.shape == (3,)
    assert (err >= 0).all()


def test_autoencoder_training_step_reduces_loss():
    torch.manual_seed(0)
    model = LSTMAutoencoder(n_features=4, hidden_size=8, latent_size=4)
    x = torch.randn(16, 10, 4)
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = torch.nn.MSELoss()

    losses = []
    for _ in range(20):
        opt.zero_grad()
        recon = model(x)
        loss = loss_fn(recon, x)
        loss.backward()
        opt.step()
        losses.append(loss.item())

    assert losses[-1] < losses[0]


def test_rul_predictor_forward_shape_and_bounds():
    model = RULRegressorGRU(n_features=6, hidden_size=8, num_layers=1)
    x = torch.randn(7, 24, 6)
    out = model(x)
    assert out.shape == (7,)
    assert torch.all(out >= 0.0) and torch.all(out <= 1.0)


def test_spectral_baseline_detector_separates_normal_from_extreme():
    rng = np.random.default_rng(0)
    normal = rng.normal(loc=0.0, scale=1.0, size=(200, 11))
    detector = SpectralBaselineDetector(contamination=0.05).fit(normal)

    normal_scores = detector.score_batch(rng.normal(loc=0.0, scale=1.0, size=(50, 11)))
    extreme_scores = detector.score_batch(
        rng.normal(loc=15.0, scale=1.0, size=(50, 11))
    )

    assert extreme_scores.mean() > normal_scores.mean()
