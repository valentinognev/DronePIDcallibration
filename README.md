# PIDToolBox

A modern web reimplementation of [PIDtoolbox](https://github.com/bw1129/PIDtoolbox) / [PIDscope](Refs/PIDscope/) for multirotor PID tuning from blackbox flight logs. The mathematical backend is **Python** (FastAPI, NumPy, SciPy); the UI is **React + TypeScript + Tailwind + Plotly.js**.

**Current version:** `0.1.33`  
**Status:** Functional prototype with all major analysis tools scaffolded; UI and algorithm parity with the original MATLAB app is incomplete in places (see [Known gaps](#known-gaps--next-work) below). Recent work: **System ID** tab (quadrotor parameter estimation from flight logs); Spectral Analyzer RPM/dynamic-notch overlays; persistent tab state (`PersistentRoutes`); PX4 ULOG motors (see [UPDATES.md](UPDATES.md)).

---

## Quick start

Requires **Python 3.11+**, **Node.js 20+**, **npm**, **git**, **gcc**, and **make** on the host (no Docker).

```bash
./install.sh   # once: builds blackbox_decode, venv, deps, tests, frontend build
./start.sh     # backend :8000 + frontend :5173
./kill.sh      # stop both servers
```

`install.sh` is self-contained: it clones and compiles [Betaflight blackbox-tools](https://github.com/betaflight/blackbox-tools) into `tools/bin/blackbox_decode` and writes `.pidbox.env` for `start.sh`. No system-wide install required.

Open **http://localhost:5173** in a browser. The Vite dev server proxies `/api` to the FastAPI backend.

---

## Project layout

```
PIDToolBox/
├── install.sh              # First-time setup
├── start.sh                # Run backend + frontend
├── UPDATES.md              # Changelog — MANDATORY reading for agents (see bottom)
├── README.md               # This file
├── backend/
│   ├── pyproject.toml
│   ├── pidbox/
│   │   ├── main.py         # FastAPI entry point
│   │   ├── session.py      # In-memory sessions + Parquet cache
│   │   ├── config.py       # Paths, env vars
│   │   ├── api/            # REST routers
│   │   └── core/           # Math + parsers (mirrors Refs/PIDscope/src/core/)
│   └── tests/              # pytest + golden fixtures
├── frontend/
│   ├── src/
│   │   ├── pages/          # One page per analysis tool
│   │   ├── components/     # Shared UI
│   │   ├── store/          # Zustand session store
│   │   └── lib/api.ts      # Typed API client
│   └── vite.config.ts      # Dev proxy → localhost:8000
├── Refs/                   # READ-ONLY reference (do not modify unless asked)
│   ├── PIDscope/           # Octave port — source of truth for algorithms
│   ├── ScreenShotsShort/   # Target UI screenshots
│   └── ScreenShotsLong/
├── Docs/
│   └── pidtoolbox_react_clone_f16620bf.plan.md   # Original implementation plan
└── .github/workflows/ci.yml
```

---

## Architecture

```
Browser (React + Plotly)
    │  HTTP  /api/*
    ▼
FastAPI (uvicorn :8000)
    ├── session_manager  — uploaded files, parsed DataFrames in memory
    ├── blackbox_decode  — subprocess for .BBL/.BFL → CSV
    └── core/*           — NumPy/SciPy analysis (ports of PIDscope .m files)
```

Sessions are ephemeral (in-memory). A backend restart clears all sessions — the UI recreates a session automatically on load/upload (do not rely on a persisted session id). Parsed data can be cached as Parquet under `~/.cache/pidbox/`. User defaults persist to `~/.cache/pidbox/defaults.json`.

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PIDBOX_DATA_DIR` | `~/.cache/pidbox` | Upload cache, settings |
| `BLACKBOX_DECODE` | `blackbox_decode` | Path to Betaflight decoder |
| `BLACKBOX_DECODE_INAV` | `blackbox_decode_INAV` | Path to INAV decoder |

---

## Backend API

Base URL: `http://localhost:8000/api`

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/sessions/firmwares` | List supported firmware parsers |
| POST | `/sessions` | Create session `{ "firmware": "betaflight" }` |
| GET | `/sessions/{id}` | Session info + uploaded files |
| DELETE | `/sessions/{id}` | Delete session |
| POST | `/sessions/{id}/files` | Upload log file (multipart) |
| POST | `/sessions/{id}/traces` | Get log viewer time-series |
| PATCH | `/sessions/{id}/files/{fi}/logs/{li}/epoch` | Set analysis time window |
| GET | `/sessions/{id}/files/{fi}/logs/{li}/setup` | Setup info key/value pairs |

### Analysis

| Method | Path | PIDscope source |
|--------|------|-----------------|
| POST | `/analysis/spectrum` | PSSpec2d + notch overlays |
| POST | `/analysis/overlay-capabilities` | RPM/dyn-notch data probe |
| POST | `/analysis/step-response` | PSstepcalc |
| POST | `/analysis/throttle-spectrum` | PSthrSpec + PSestimateRPM |
| POST | `/analysis/time-freq` | PStimeFreqCalc |
| POST | `/analysis/filter-sim` | PSbfFilters |
| POST | `/analysis/stats` | PSplotStats (simplified) |
| POST | `/analysis/chirp` | PSestimateFreqResponse |
| POST | `/analysis/setup-diff` | PSdispSetupInfo diff view |
| POST | `/analysis/sysid/capabilities` | Motor/accel/gyro column probe |
| POST | `/analysis/sysid/defaults` | Mass + rotor geometry from log |
| POST | `/analysis/sysid/preview` | Excitation metrics per file |
| POST | `/analysis/sysid/run` | Full estimation pipeline |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET/PUT | `/settings` | User defaults (theme, line width, etc.) |

Interactive API docs: **http://localhost:8000/docs**

---

## PIDscope → Python module map

When porting or validating algorithms, always compare against `Refs/PIDscope/src/`:

| Octave/MATLAB | Python | Notes |
|---------------|--------|-------|
| `PSSpec2d.m` | `core/spectral.py::psd_2d` | Manual Hann+FFT, **not** scipy.welch |
| `PSthrSpec.m` | `core/spectral.py::throttle_spectrum` | 300 ms segments, throttle bins 1–100 |
| `PStimeFreqCalc.m` | `core/spectral.py::time_freq_calc` | |
| `PSstepcalc.m` | `core/stepresponse.py::step_calc` | Wiener deconv, QC gate 0.5–3 |
| `PSbfFilters.m` | `core/filters.py::bf_filter_coeffs` | pt2 factor `1.553773974`, pt3 `1.961459177` |
| `PSestimateFreqResponse.m` | `core/chirp.py::estimate_freq_response` | Welch CSD |
| `PSestimateRPM.m` | `core/rpm.py::estimate_rpm` | |
| `PSplotRPMOverlay.m` | `core/notch_overlays.py` | RPM + dyn notch harmonic overlays |
| Motor noise harmonics | `core/motor_noise_harmonics.py` | Spectral Analyzer secondary view |
| `PSload.m`, `PSimport.m`, `PSgetcsv.m` | `core/parsers/*`, `core/loader.py` | |
| `PSdebugModeIndices.m` | `core/debug_modes.py` | BF 2025.12+ index shifts |
| Berkeley `sysid.py` | `core/sysid/*` | Data-driven quadrotor ID (not PIDscope); see [System ID](#system-id-sysidpage) |
| `plot/*.m`, `ui/*.m` | `frontend/src/pages/*` | Rendering is Plotly, not MATLAB |

---

## Frontend pages

| Route | Component | Original tool |
|-------|-----------|---------------|
| `/` | `LogViewerPage` | Main log viewer |
| `/spectral` | `SpectralAnalyzerPage` | Spectral Analyzer |
| `/step-response` | `StepResponsePage` | Step Resp Tool |
| `/freq-throttle` | `FreqThrottlePage` | Frequency × Throttle |
| `/freq-time` | `FreqTimePage` | Frequency × Time |
| `/filter-sim` | `FilterSimPage` | Filter Sim |
| `/setup-info` | `SetupInfoPage` | Setup Info diff |
| `/stats` | `StatsPage` | PID Stats |
| `/sysid` | `SysIdPage` | System ID (quadrotor parameter estimation) |

Global state: `frontend/src/store/sessionStore.ts` (Zustand + localStorage for UI prefs).

**Tab persistence:** `PersistentRoutes` keeps visited pages mounted so plots and **Run** results survive tab switches; `Plot` resizes when a tab becomes visible again.

### Log Viewer (`LogViewerPage`)

| Area | Behavior |
|------|----------|
| **Firmware** | Betaflight family, INAV, ArduPilot, QuickSilver, **PX4** (`.ulg` via `pyulog`). Upload auto-selects firmware: `.ulg` → PX4, `.bbl`/`.bfl`/`.btfl` → Betaflight. |
| **Selection panel** (left) | Trace checkboxes with colors; toggling refetches traces and **autoscales** Y on X/Y/Z panels. |
| **Plots** | Three axis panels (body X/Y/Z → roll/pitch/yaw data columns). Titles are signal-specific (e.g. `Roll rate`, `AccX`, `Vx_SP`); Y-axis label shows units only. |
| **Analysis window** | Dual-handle slider above plots (`EpochRangeSlider`); sets epoch for all tools. No draggable trim handles on plots (avoids blocking zoom). |
| **Control panel** (right) | Firmware, file picker, **X / Y / Z** panel visibility, line smooth/width, theme, save settings. |
| **Helpers** | `computeTraceYRange`, `buildPanelCaption`, `tracePanelTitle` in `frontend/src/lib/utils.ts` / `constants.ts`. |
| **Trace toggles** | Rapid channel on/off no longer leaves ghost curves (Plotly remount + `refreshTraces` request sequencing + `pruneTraceData()`). |
| **PX4 traces** | Extra toggles: accel, attitude, velocity, **motor input** (`motor_in_*`). Motor RPM uses `eRPM_*` from ESC when logged (see [PX4 ULOG motors](#px4-ulog-motors)). |
| **Motor / throttle panel** | Throttle + up to four motors; RPM on secondary Y when `eRPM_*` present, else PWM as percent. |

### Spectral Analyzer (`SpectralAnalyzerPage`)

| Area | Behavior |
|------|----------|
| **Grid** | Per visible axis (R/P/Y): **Full Spectrum** + secondary panel (**sub-100 Hz** or **Motor Noise**). External Y/X labels on each panel (matches Filter Sim / Freq×Throttle). |
| **Traces** | Signal checkboxes: gyro, gyro prefilt, D/P/I terms, PID error, setpoint. Motors are **not** spectrum traces — use the motor grid for notch overlays. |
| **Multi-file** | Up to 10 files; color per trace, dash per file (`FILE_OVERLAY_LINE_DASHES`); legend `F1 · Gyro` when comparing logs. |
| **Control panel** | Smoothing, **R / P / Y**, **PSD** toggle, Y min/max (defaults −50…20 dB PSD / 0…0.5 amplitude), 2×2 motor grid (M4/M2 / M3/M1), **RPM notch** and **Dyn notch** dropdowns, **RPM est.** + multiplier, secondary view selector. |
| **RPM notch overlays** | Harmonic center lines on Full Spectrum when PSD on. Sources: `RPM_FILTER` debug, else eRPM; **RPM est.** uses motor-spectrum estimate. Dropdown auto-disables with tooltip when log lacks data (`POST /analysis/overlay-capabilities`). |
| **Dyn notch overlays** | Filter frequency-response curves from `debug_*` when log `debug_mode == FFT_FREQ` (requires FFT_FREQ blackbox debug). |
| **Motor Noise** | Bar-style pre/post-filter harmonic averages per axis (`include_motor_noise` on spectrum run). |
| **Run** | `POST /analysis/spectrum`; overlay and smoothing changes auto re-run when results exist. Per-panel **Save** exports PNG. |

### Step Response (`StepResponsePage`)

| Area | Behavior |
|------|----------|
| **Layout** | Per axis (Roll/Pitch/Yaw): main step curve (75% width) + peak/latency bars and stats (25%). |
| **Signal modes** | Checkboxes: Rate, Attitude, Velocity, Accel — all selected modes overlay on the same axis plot. |
| **Curve styling** | Color = file; line dash/width = signal (`STEP_SIGNAL_LINE_STYLES`). Bar fill uses matching hatch patterns (`STEP_SIGNAL_BAR_PATTERNS`). |
| **Multi-file** | Up to 10 files; legend names include file when comparing logs. |
| **Backend** | `POST /analysis/step-response` with `signals[]`. Accel deconvolution uses **velocity setpoint** as input; per-signal `min_input` and QC tuned for m/s and m/s² scales. |
| **Run** | Click **Run** after changing signal modes or files; file checkboxes filter displayed results immediately. |

### System ID (`SysIdPage`)

Quadrotor parameter estimation ported from the Berkeley reference workflow ([sysid.tools](https://sysid.tools)). Algorithms follow **Data-Driven System Identification of Quadrotors Subject to Motor Delays** (cited in the UI summary).

| Area | Behavior |
|------|----------|
| **Reference** | Motor delay + thrust / inertia / yaw torque identification from excitation logs; uses parsed session columns (`accel_*`, `gyroADC_*`, motor commands) — no separate log loader. |
| **Phases** | Three panels: thrust/motor model, roll–pitch inertia, yaw torque — each with file dropdown, **Enabled** toggle, epoch range slider, and excitation preview plot. |
| **Sidebar** | Geometry source log, mass, inertia ratio, 4× rotor pos/thrust/torque (FLU), **Run estimation**. |
| **Results summary** | Below **Run estimation**: `Tm`, thrust RMSE, **d** (`T = d·(ω₁²+ω₂²+ω₃²+ω₄²)`), hover thrust / Σωᵢ², `Ixx`/`Iyy`/`Izz`, `Kτ`, model inputs, paper reference. |
| **Diagnostic plots** | Tm search curve; **thrust vs ω²** (x = Σωᵢ², fit `T = d·Σωᵢ²`); thrust fit; hover-throttle histogram; inertia scatter; yaw `Kτ`. Result plots use static Plotly mode for scroll performance. |

**ω₁…ω₄ in the thrust model:** per-motor **normalized motor commands** after a first-order EMA with estimated `Tm` (`core/sysid/dynamics.py` → `rpms`). Sources: `motor_in_*` (0–1), `motor_*` PWM %, or normalized `eRPM_*`. These are **not** gyro body rates (`omega` from `gyroADC_*` is used only for inertia/yaw steps).

**Backend modules:** `core/sysid/log_adapter.py`, `preprocess.py`, `dynamics.py`, `estimators.py`, `excitation.py`, `pipeline.py`, `rotor_model.py`. Tests: `backend/tests/test_sysid.py`.

---

## Supported firmware parsers

Registered in `core/parsers/` via `@register_parser`:

| Key | File | Input formats |
|-----|------|---------------|
| `betaflight` | `betaflight.py` | `.bbl`, `.bfl`, `.csv`, `.txt`, `.btfl` |
| `emuflight` | subclass of betaflight | same |
| `fettec` | subclass of betaflight | same |
| `rotorflight` | subclass of betaflight | same |
| `kiss` | subclass of betaflight | same |
| `inav` | `inav.py` | `.bbl`, `.bfl`, `.csv` (uses INAV decoder) |
| `quicksilver` | `quicksilver.py` | `.json`, `.btfl` |
| `ardupilot` | `ardupilot.py` | `.bin`, `.log` |
| `px4` | `px4.py` | `.ulg` (ULOG via `pyulog`) |

To add a parser: create a class extending `LogParser` in `core/parsers/`, decorate with `@register_parser`, import it in `core/parsers/__init__.py` and `core/loader.py`.

### PX4 ULOG motors

PX4 logs do not use Betaflight column names. At **load time** the parser scans topics and maps up to four logical motors (`0`…`3`). Physical channel indices vary by airframe and are stored in log metadata / Setup Info.

| Signal | ULOG topic | Field | DataFrame columns | Trace keys | UI |
|--------|------------|-------|-------------------|------------|-----|
| **RPM (measured)** | `esc_status` | `esc[N].esc_rpm` | `eRPM_0_`…`eRPM_3_` | `motor_0`…`motor_3` | Log Viewer, Spectral Analyzer (preferred when present) |
| **Motor input** | `actuator_motors` | `control[N]` | `motor_in_0_`…`motor_in_3_` (0–100%) | `motor_in_0`…`motor_in_3` | Log Viewer only |
| **PWM output** | `actuator_outputs` | `output[N]` | `motor_0_`…`motor_3_` (scaled to %) | fallback for `motor_*` if no `eRPM_*` | — |

**Discovery:** a channel is “active” if its sample std exceeds a firmware-specific threshold (RPM > 10, control > 0.01, PWM > 1). Idle/disarmed slots are skipped.

**Implementation:** `backend/pidbox/core/parsers/px4.py` (`_load_motors`, `_discover_*`); traces in `backend/pidbox/core/traces.py` (`TRACE_DEFS`).

**After parser changes:** re-upload `.ulg` files so sessions pick up new columns.

---

## Development

### Backend only

```bash
cd backend
source .venv/bin/activate
uvicorn pidbox.main:app --reload --port 8000
pytest -v
python tests/export_golden.py   # regenerate golden .npz fixtures
```

### Frontend only

```bash
cd frontend
npm run dev
npm test
npm run build
```

### CI

GitHub Actions runs backend pytest, frontend vitest, and production build on push/PR to `main`/`master`.

---

## Testing strategy

1. **Unit tests** — `backend/tests/test_*.py` (79 tests covering spectral, notch overlays, step response, filters, chirp, rpm, traces, stats, API).
2. **Golden data** — `backend/tests/fixtures/golden/*.npz` generated by `export_golden.py`. Goal: extend with outputs from Octave running `Refs/PIDscope/tests/` on real logs, assert RMSE ≤ 1e-4.
3. **Frontend** — `frontend/src/lib/constants.test.ts`, `frontend/src/lib/utils.test.ts` (vitest). Playwright E2E not yet implemented.

When changing any `core/*.py` algorithm, run `pytest` and update golden fixtures if intentional behavior change.

---

## Known gaps / next work

Priority items for the next agent (also tracked in `UPDATES.md`):

1. **Install `blackbox_decode`** on dev machines or bundle it in `install.sh`.
2. **Validate algorithms** against Octave/PIDscope on real `.bbl` logs from `Refs/PIDscope/tests/`.
3. **UI parity** — compare each page to `Refs/ScreenShotsShort/` and `Refs/ScreenShotsLong/`:
   - Log viewer: period/markup tool, debug mode overlay (analysis-window slider and PX4 traces are in place; plot-level epoch drag handles were removed intentionally).
   - Spectral analyzer: markup tool, remaining dropdown states from reference screenshots; dyn notch needs `FFT_FREQ` debug in log.
   - Freq×Throttle: multi-column grid (one trace per column) like original.
   - Step response: error-bar style peak/latency vs reference screenshots; validate velocity/accel on real PX4 logs.
   - Missing tools: PID slider tool, dedicated Bode/chirp page.
4. **Implement pure-Python BBL parser** in `core/parsers/bbl_native.py` (replace subprocess dependency).
5. **Wire save-figure** on remaining pages — Spectral Analyzer and Log Viewer (roll panel) have Save; other tools still pending.
6. **WebSocket progress** — stub exists; connect to long-running spectrogram jobs.
7. **Licensing** — decide GPL-3.0 (recommended, derivative of PIDscope) before public release.
8. **Tauri desktop bundle** — optional offline wrapper around built frontend + embedded uvicorn.

---

## Reference material (read-only)

- **`Refs/PIDscope/`** — Complete Octave implementation. When in doubt about algorithm behavior, read the corresponding `.m` file here.
- **`Refs/ScreenShotsShort/`** — Compact UI reference screenshots.
- **`Refs/ScreenShotsLong/`** — Detailed UI with dropdown states.
- **`Docs/pidtoolbox_react_clone_f16620bf.plan.md`** — Phased implementation plan (phases 0–8 marked complete; polish items partially done).

Do **not** modify files under `Refs/` unless explicitly requested.

---

## Agent handoff checklist

Before starting work, an agent should:

1. Read this README fully.
2. **Read [UPDATES.md](UPDATES.md) — mandatory.** It contains the versioned changelog and documents every change made so far.
3. Skim `Docs/pidtoolbox_react_clone_f16620bf.plan.md` for original intent.
4. Run `./install.sh` to verify the environment.
5. Run `./start.sh` and smoke-test at least the Log Viewer with a CSV log.
6. After completing work:
   - Run `pytest` and `npm test && npm run build`.
   - **Append a new entry to the top of `UPDATES.md`** with bumped version (`major.subversion.subsubversion`), date, and descriptions of all additions/fixes/removals.
   - Bump version strings in `backend/pidbox/main.py` and `backend/pidbox/__init__.py` if releasing a new version.

### Version numbering rules (for UPDATES.md)

- Format: `X.Y.Z` (e.g. `0.1.0`, `0.1.1`, `0.2.0`, `1.0.0`).
- **Newest entry always at the top** of `UPDATES.md`, below the header.
- Increment **Z** (subsubversion) for bug fixes and small changes.
- Increment **Y** (subversion) for new features or significant UI work.
- Increment **X** (major) for breaking API changes or first stable release.
- Every agent session that modifies code **must** add an UPDATES.md entry — no exceptions.

---

## Mandatory reading

> **All agents continuing work on this project must read [UPDATES.md](UPDATES.md) before making changes and must maintain it after every session.**  
> `UPDATES.md` is the authoritative changelog: version history, what was added, fixed, removed, and known gaps. Keep version numbering as `major.subversion.subsubversion` with the newest entry at the top.
