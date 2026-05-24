#!/usr/bin/env python3
"""Export golden reference fixtures from synthetic signals for validation."""

from pathlib import Path

import numpy as np

from pidbox.core.spectral import psd_2d
from pidbox.core.stepresponse import step_calc

OUT = Path(__file__).parent / "fixtures" / "golden"
OUT.mkdir(parents=True, exist_ok=True)


def export_psd_sine():
    fs = 4.0
    n = 2048
    t = np.arange(n) / (fs * 1000)
    y = np.sin(2 * np.pi * 100 * t)
    freqs, spec = psd_2d(y, fs, psd=True)
    np.savez(OUT / "psd_sine.npz", y=y, f_khz=fs, freqs=freqs, spec=spec)


def export_step_response():
    lograte = 4.0
    n = int(lograte * 2000 * 5)
    sp = np.zeros(n)
    gy = np.zeros(n)
    seg = int(lograte * 2000)
    sp[seg : seg + 800] = 40
    gy[seg : seg + 800] = 40 * (1 - np.exp(-np.arange(800) / 100))
    resp, t = step_calc(sp, gy, lograte)
    np.savez(OUT / "step_response.npz", sp=sp, gy=gy, lograte=lograte, resp=resp, t=t)


if __name__ == "__main__":
    export_psd_sine()
    export_step_response()
    print(f"Exported golden fixtures to {OUT}")
