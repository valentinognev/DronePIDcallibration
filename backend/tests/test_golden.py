"""Golden-data validation harness.

Compare Python outputs against reference .npz files generated from Octave/PIDscope.
To regenerate references (requires Octave):
  cd Refs/PIDscope/tests && octave --eval "run_tests"
Then export fixtures to backend/tests/fixtures/golden/
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pidbox.core.spectral import psd_2d
from pidbox.core.stepresponse import step_calc

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def _load_golden(name: str) -> dict | None:
    path = FIXTURES / f"{name}.npz"
    if not path.exists():
        return None
    return dict(np.load(path, allow_pickle=True))


@pytest.mark.parametrize("fixture", ["psd_sine", "step_response"])
def test_golden_fixture(fixture: str):
    golden = _load_golden(fixture)
    if golden is None:
        pytest.skip(f"Golden fixture {fixture}.npz not found - run Octave export first")

    if fixture == "psd_sine":
        y = golden["y"]
        f_khz = float(golden["f_khz"])
        freqs, spec = psd_2d(y, f_khz, psd=True)
        np.testing.assert_allclose(freqs, golden["freqs"], rtol=1e-6)
        np.testing.assert_allclose(spec, golden["spec"], rtol=1e-4, atol=1e-3)

    elif fixture == "step_response":
        sp = golden["sp"]
        gy = golden["gy"]
        lograte = float(golden["lograte"])
        resp, t = step_calc(sp, gy, lograte)
        if golden["resp"].shape[0] > 0 and resp.shape[0] > 0:
            n = min(resp.shape[0], golden["resp"].shape[0])
            np.testing.assert_allclose(resp[:n], golden["resp"][:n], rtol=1e-3, atol=1e-2)


def test_generate_synthetic_golden():
    """Self-test that creates synthetic data matching expected algorithm behavior."""
    fs = 4.0
    n = 2048
    t = np.arange(n) / (fs * 1000)
    y = np.sin(2 * np.pi * 100 * t) + 0.01 * np.random.randn(n)
    freqs, spec = psd_2d(y, fs, psd=True)
    assert freqs[-1] <= fs * 1000 / 2
    assert np.isfinite(spec).all()
