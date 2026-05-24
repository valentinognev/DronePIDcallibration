# PIDToolBox

A modern web reimplementation of [PIDtoolbox](https://github.com/bw1129/PIDtoolbox) / [PIDscope](Refs/PIDscope/) for multirotor PID tuning from blackbox flight logs. The mathematical backend is **Python** (FastAPI, NumPy, SciPy); the UI is **React + TypeScript + Tailwind + Plotly.js**.

**Current version:** `0.1.0`  
**Status:** Functional prototype with all major analysis tools scaffolded; UI and algorithm parity with the original MATLAB app is incomplete in places (see [Known gaps](#known-gaps--next-work) below).

---

## Quick start

Requires **Python 3.11+**, **Node.js 20+**, and **npm** on the host (no Docker).

```bash
./install.sh   # once: venv, deps, tests, frontend build
./start.sh     # backend :8000 + frontend :5173
```

Open **http://localhost:5173** in a browser. The Vite dev server proxies `/api` to the FastAPI backend.

For `.BBL` / `.BFL` files, install [Betaflight blackbox tools](https://github.com/betaflight/blackbox-tools) and ensure `blackbox_decode` is on your `PATH`. CSV logs work without it.

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

Sessions are ephemeral (in-memory). Parsed data can be cached as Parquet under `~/.cache/pidbox/`. User defaults persist to `~/.cache/pidbox/defaults.json`.

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
| POST | `/analysis/spectrum` | PSSpec2d |
| POST | `/analysis/step-response` | PSstepcalc |
| POST | `/analysis/throttle-spectrum` | PSthrSpec + PSestimateRPM |
| POST | `/analysis/time-freq` | PStimeFreqCalc |
| POST | `/analysis/filter-sim` | PSbfFilters |
| POST | `/analysis/stats` | PSplotStats (simplified) |
| POST | `/analysis/chirp` | PSestimateFreqResponse |
| POST | `/analysis/setup-diff` | PSdispSetupInfo diff view |

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
| `PSload.m`, `PSimport.m`, `PSgetcsv.m` | `core/parsers/*`, `core/loader.py` | |
| `PSdebugModeIndices.m` | `core/debug_modes.py` | BF 2025.12+ index shifts |
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

Global state: `frontend/src/store/sessionStore.ts` (Zustand + localStorage for UI prefs).

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

To add a parser: create a class extending `LogParser` in `core/parsers/`, decorate with `@register_parser`, import it in `core/parsers/__init__.py` and `core/loader.py`.

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

1. **Unit tests** — `backend/tests/test_*.py` (24 tests covering spectral, step response, filters, chirp, rpm, API).
2. **Golden data** — `backend/tests/fixtures/golden/*.npz` generated by `export_golden.py`. Goal: extend with outputs from Octave running `Refs/PIDscope/tests/` on real logs, assert RMSE ≤ 1e-4.
3. **Frontend** — `frontend/src/lib/constants.test.ts` (vitest). Playwright E2E not yet implemented.

When changing any `core/*.py` algorithm, run `pytest` and update golden fixtures if intentional behavior change.

---

## Known gaps / next work

Priority items for the next agent (also tracked in `UPDATES.md`):

1. **Install `blackbox_decode`** on dev machines or bundle it in `install.sh`.
2. **Validate algorithms** against Octave/PIDscope on real `.bbl` logs from `Refs/PIDscope/tests/`.
3. **UI parity** — compare each page to `Refs/ScreenShotsShort/` and `Refs/ScreenShotsLong/`:
   - Log viewer: interactive epoch trim (drag handles), period/markup tool, debug mode overlay.
   - Spectral analyzer: multi-file overlay colors, motor pair toggles, RPM overlay.
   - Freq×Throttle: multi-column grid (one trace per column) like original.
   - Step response: peak/latency bar charts per original layout.
   - Missing tools: PID slider tool, dedicated Bode/chirp page.
4. **Implement pure-Python BBL parser** in `core/parsers/bbl_native.py` (replace subprocess dependency).
5. **Wire save-figure** — `frontend/src/lib/utils.ts::savePlotlyFigure` exists but is not hooked up to UI buttons.
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
