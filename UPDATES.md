# PIDToolBox — Update Log

Version format: **major.subversion.subsubversion** (e.g. `0.1.0`).  
Newest entry always at the top. Every agent must append an entry here when making changes.

---

## 0.1.19 — 2026-05-29

### Added

- **Step Response multi-signal overlay**: one plot per axis (Roll/Pitch/Yaw) overlays all selected signal modes (Rate, Attitude, Velocity, Accel) on a single file or multiple files. Line dash/width per mode (`STEP_SIGNAL_LINE_STYLES`); bar hatch patterns per mode (`STEP_SIGNAL_BAR_PATTERNS`, `stepSignalBarMarker()`).
- **Step Response layout**: 75% / 25% grid for step curve vs peak/latency/stats; HTML headings on right-column charts; Y numeric ticks kept, X file labels hidden (colors/legend on main plot).
- **Log Viewer trace toggle reliability**: Plotly remount key on visible trace set; stale `refreshTraces` responses ignored; `pruneTraceData()` drops hidden series from session state.

### Fixed

- **Step Response bar charts**: numeric X positions prevent stacked bars when truncated filenames collide; `barmode: 'group'`.
- **Step Response file selection**: plots filter by checked files without requiring a new Run after unchecking.
- **Velocity / Accel step response** (`analysis.py`, `stepresponse.py`): signal-specific `min_input` thresholds (rate 20, attitude 5°, velocity 0.5 m/s, accel 0.25 m/s); accel uses **velocity setpoint** as excitation (logs lack accel SP); relaxed QC gate (0.05–5) for non-rate signals. Test: `test_step_response_velocity_and_accel_signals`.

### Changed

- API / UI version `0.1.19`.

---

## 0.1.18 — 2026-05-28

### Removed

- **Log Viewer y scale field**: removed the unused **y scale** input from the Selection panel; X/Y/Z panels rely on trace autoscale only (`computeTraceYRange`). Removed `yScale` from `AppSettings` / persisted store.

### Documentation

- **README.md**: version `0.1.18`, Log Viewer behavior table, PX4 in firmware list, known-gaps note on epoch slider vs plot drag handles.
- UI version `v0.1.18`.

---

## 0.1.17 — 2026-05-28

### Changed

- **Log Viewer control panel**: axis visibility toggles labeled **X, Y, Z** (was R, P, Y); still map to roll/pitch/yaw panels.
- UI version `v0.1.17`.

---

## 0.1.16 — 2026-05-28

### Changed

- **Log Viewer plot titles (ISSUE-012)**: R/P/Y figure titles use signal-specific names per panel axis — rate: Roll/Pitch/Yaw rate (+ `SP` for setpoint); attitude: Roll/Pitch/Yaw (+ `SP`); accel: AccX/AccY/AccZ; velocity: Vx/Vy/Vz (+ `SP`). Y-axis labels show units only (no redundant axis prefix).
- **`tracePanelTitle()`** in `constants.ts`.
- API / UI version `0.1.16`.

---

## 0.1.15 — 2026-05-28

### Changed

- **Log Viewer dynamic plot titles (ISSUE-011)**: Roll, Pitch, Yaw, and motor/throttle figure titles and Y-axis labels update when channels are toggled (e.g. `Roll — Gyro, Attitude` with `Roll (deg/s, deg)`). Motor panels list visible motor/throttle traces and units.
- **`buildPanelCaption()` / `buildMotorPanelCaption()`** in `frontend/src/lib/utils.ts`; **`TRACE_Y_UNITS`** in `constants.ts`.
- API / UI version `0.1.15`.

---

## 0.1.14 — 2026-05-28

### Changed

- **Log Viewer Y autoscale (ISSUE-010)**: Roll, Pitch, and Yaw panels recompute Y-axis limits from visible traces whenever a channel is toggled on or off (5% padding). (Fixed `±y scale` fallback removed in `0.1.18`.)
- **`computeTraceYRange()`** in `frontend/src/lib/utils.ts` with unit tests.
- API / UI version `0.1.14`.

---

## 0.1.13 — 2026-05-28

### Fixed

- **Log Viewer Roll plot vertical zoom (ISSUE-009)**: Y-axis zoom/box-zoom works on the top (Roll) panel again after loading PX4 `.ulg` logs (and all other logs). Removed draggable epoch-trim shapes from the Roll plot; they captured pointer events over the full plot height. Analysis window is set only via the **Analysis window** slider above the plots (`EpochRangeSlider`).
- API / UI version `0.1.13`.

---

## 0.1.12 — 2026-05-28

### Fixed

- **PX4 Log Viewer trace toggles (ISSUE-008)**: PX4 channels (`accel`, `attitude`, `attitude_sp`, `velocity`, `velocity_sp`) can be unchecked again after loading a `.ulg` file. `refreshTraces()` no longer re-enables every available PX4 trace on each fetch; it only auto-enables traces that were not present in the previous `available_traces` list (first discovery after upload).
- API / UI version `0.1.12`.

---

## 0.1.11 — 2026-05-28

### Fixed

- **PX4 Log Viewer + Step Response UI (ISSUE-007)**: frontend now requests and renders PX4 accel/attitude/velocity traces that the backend already exposes.
  - **`sessionStore.ts`**: removed hard filter to Betaflight-only `DEFAULT_TRACES` in `refreshTraces()`; requests intersection of `visibleTraces` with `available_traces`, pre-includes PX4 keys on first fetch, and auto-enables newly discovered PX4 traces in the toggle panel.
  - **`constants.ts`**: labels/colors for `accel`, `attitude`, `attitude_sp`, `velocity`, `velocity_sp`; shared `PX4_EXTRA_TRACES`, `DEFAULT_TRACES`, and `STEP_SIGNAL_MODES`.
  - **`StepResponsePage.tsx`**: signal-mode checkboxes (Rate, Attitude, Velocity, Accel); passes `signals` to `/analysis/step-response`; renders `results[].signals[mode][axis]` with backward-compatible `axes` for rate-only.
  - **`api.ts`**: typed `StepResponseRequest` / `StepResponseResult`.
- UI version badge `v0.1.11`.

---

### Added

- **PX4 ULG accel/attitude/velocity traces (ISSUE-006)**: Log Viewer and Step Response support for PX4 channels beyond gyro rate.
  - **Parser (`px4.py`)**: interpolates accelerometer to gyro timeline from `sensor_accel_fifo`, `sensor_combined`, or `vehicle_acceleration` into `accel_0_/1_/2_` (m/s²). Loads `vehicle_local_position` vx/vy/vz and setpoints from `vehicle_local_position_setpoint` or `trajectory_setpoint` into `vel_*` / `vel_sp_*` (NED, m/s). Units and frame documented in log metadata.
  - **Traces (`traces.py`)**: new trace keys `accel`, `attitude`, `attitude_sp`, `velocity`, `velocity_sp`; exposed via `list_available_traces()` when columns exist.
  - **Step Response API**: `StepResponseRequest.signals` list (`rate`, `attitude`, `velocity`, `accel`; default `["rate"]`). Multi-signal responses use `signals.{mode}.{axis}`; default rate-only keeps backward-compatible `axes` shape. Accel mode uses zero setpoint (empty curves when no steps detected).
- **`backend/tests/test_step_response_api.py`**: attitude signal and backward-compat coverage.
- Extended **`test_px4_parser.py`** and **`test_traces.py`** for new columns and trace keys.

### Changed

- API version `0.1.10`.

---

## 0.1.9 — 2026-05-28

### Fixed

- **Empty epoch slice on `/traces` (PID-005)**: requesting traces for an epoch window outside the log's time span no longer returns HTTP 500. The API responds with HTTP 200 and empty trace panels while preserving epoch bounds, metadata, and `full_time_range` from the full log.

### Changed

- API version `0.1.9`.

---

## 0.1.8 — 2026-05-28

### Fixed

- **PX4 ULOG UI (ISSUE-003)**: Log Viewer now supports `.ulg` files and PX4 firmware selection.
  - `FileDropzone` accept filter includes `.ulg` (via shared `LOG_FILE_ACCEPT` constant).
  - Firmware dropdown populated from `GET /sessions/firmwares` with `FALLBACK_FIRMWARES` fallback (includes PX4).
  - Changing firmware in Control Panel creates a new backend session and clears loaded files/trace state.
  - Uploading any `.ulg` file auto-switches to PX4 firmware (recreates session if needed) before upload.
- **Empty-parse upload rejection (ISSUE-004)**: uploads that yield zero logs now return HTTP 400 immediately with an actionable message instead of succeeding and failing later on `/traces`.
  - Base message: "No logs could be parsed from this file."
  - `.ulg` on non-PX4 sessions hints to use firmware `px4`.
  - When another registered parser recognizes the extension, the error suggests the matching firmware key(s).
  - No `SessionFile` is added; partial upload bytes are removed from the session directory.
- **`backend/tests/test_upload_empty_parse.py`**: API and message-builder coverage for empty-parse rejection.

### Changed

- API version `0.1.8`.

---

## 0.1.7 — 2026-05-28

### Added

- **Spectral Analyzer (ISSUE-001)**: Trace parameter labels in the Params panel are colorized with `getTraceColor()` to match spectrum plot curves, consistent with Log Viewer `TraceTogglePanel`. Shared `TRACE_LABELS` moved to `constants.ts`.
- **PX4 ULOG parser (ISSUE-002)**: new `px4` firmware key accepts `.ulg` files via `pyulog`.
  - Prefers high-rate `sensor_gyro_fifo` / `sensor_accel_fifo` when present; falls back to `sensor_combined` or `vehicle_angular_velocity`.
  - Maps `vehicle_rates_setpoint`, attitude topics, and `vehicle_thrust_setpoint` into standard `gyroADC_*` / `setpoint_*` columns (rad→deg/s).
  - Extracts up to 200 ULOG parameters into setup info.
- **`backend/tests/test_px4_parser.py`**: registration, FIFO vs combined rate, no-FIFO fallback, and mock tests.

### Changed

- **`pyproject.toml`**: added `pyulog>=1.0.0` dependency.
- **`compute_derived_columns`**: PX4 skips Betaflight-specific debug/motor zero-fill (same as ArduPilot).
- API version `0.1.7`.

---

## 0.1.6 — 2026-05-24

### Fixed

- **Default epoch (PID-001)**: short logs no longer crash traces API; default window clamped to valid bounds.
- **Session workflow (PID-002, PID-003)**: Log Viewer no longer resets session on remount; session and file metadata persist across refresh.
- **Analysis APIs (PID-004–PID-006)**: stats, spectrum, and throttle-spectrum endpoints return 200 with JSON-safe payloads.
- **UI parity (PID-008–PID-012)**: plot epoch drag handles, spectral multi-file/RPM controls, freq-throttle grid, step bar charts, save-figure buttons.
- **Version label (PID-007)**: header, health endpoint, and changelog aligned at `0.1.6`.

---

## 0.1.5 — 2026-05-24

### Fixed

- **Light theme**: Plotly figures now use light backgrounds, grid, and axis label colors matching the UI theme; white trace lines are remapped for contrast on light backgrounds.
- **Theme sync**: persisted theme applies on app load via `ThemeSync` and store rehydration.

---

## 0.1.4 — 2026-05-24

### Fixed

- **Log Viewer**: analysis window slider stays pinned above the plot area while scrolling vertically.
- **Log Viewer**: throttle and motor RPM plots no longer overlap (Plotly containers now reserve height in the flex column).

---

## 0.1.3 — 2026-05-24

### Added

- **Log Viewer analysis window slider**: dual-handle horizontal range control above the top plot to set epoch start/end; updates session epoch so all analysis tools use the selected time range only.
- **`full_time_range`** in trace API response (full log duration independent of current epoch slice).

---

## 0.1.2 — 2026-05-24

### Added

- **`kill.sh`**: stops backend (port 8000) and frontend (port 5173) started by `start.sh`.

---

## 0.1.1 — 2026-05-24

### Added

- **Self-contained `install.sh`**: clones [betaflight/blackbox-tools](https://github.com/betaflight/blackbox-tools), builds `blackbox_decode` into `tools/bin/`, writes `.pidbox.env` for `start.sh`.
- **`config.resolve_decoder_path()`**: finds decoder via env var, `tools/bin/`, or system PATH.
- **`normalize_blackbox_columns()`**: maps blackbox_decode CSV headers (`time (us)`, `gyroADC[0]`) to Octave-style names (`time_us`, `gyroADC_0_`).

### Fixed

- `.BBL`/`.BFL` upload failed with `[Errno 2] No such file or directory: 'blackbox_decode'` when decoder was not on system PATH.
- CSV parsing failed after decode because column names did not match MATLAB `readtable` sanitization.

### Changed

- `start.sh` sources `.pidbox.env` and verifies `blackbox_decode` exists before launch.
- `.gitignore` excludes `tools/blackbox-tools-src/` and `tools/bin/`.

---

## 0.1.0 — 2026-05-24

Initial implementation of the PIDToolBox React clone (Python backend + React frontend).

### Added

- **Backend (`backend/pidbox/`)**
  - FastAPI application with session management, file upload, and analysis endpoints.
  - Core signal-processing ports from PIDscope/Octave reference:
    - `core/spectral.py` — PSSpec2d, PSthrSpec, PStimeFreqCalc
    - `core/stepresponse.py` — PSstepcalc (Wiener deconvolution)
    - `core/filters.py` — PSbfFilters (pt1/pt2/pt3/biquad/notch)
    - `core/chirp.py` — PSestimateFreqResponse, PSrotFiltFilt, chirp window finder
    - `core/rpm.py` — PSestimateRPM
    - `core/stats.py` — simplified PSplotStats (PID balance, motor noise)
    - `core/traces.py` — log viewer trace extraction
    - `core/smoothing.py` — LOWESS smoothing (statsmodels)
    - `core/debug_modes.py` — PSdebugModeIndices
  - **Parsers** (`core/parsers/`):
    - Betaflight (+ Emuflight, FETTEC, Rotorflight, KISS as Betaflight subclasses)
    - INAV (via `blackbox_decode_INAV`)
    - QuickSilver (JSON → CSV)
    - ArduPilot (`.bin` via pymavlink)
    - `bbl_native.py` — stub interface for future pure-Python BBL parser
  - Log loading via `blackbox_decode` subprocess for `.BBL`/`.BFL`; direct CSV also supported.
  - Settings persistence to `~/.cache/pidbox/defaults.json`.
  - WebSocket progress stub at `/api/ws/progress/{task_id}`.

- **Frontend (`frontend/`)**
  - Vite + React 19 + TypeScript + Tailwind CSS v4 + Plotly.js.
  - Zustand session store with localStorage persistence for UI settings.
  - Pages: Log Viewer, Spectral Analyzer, Step Response, Freq×Throttle, Freq×Time, Filter Sim, Setup Info, PID Stats.
  - Dark/light theme toggle, keyboard shortcut (Ctrl+R refresh traces).
  - API client in `src/lib/api.ts` with dev proxy to backend.

- **Tooling**
  - `install.sh` — venv, pip install, npm ci, pytest, frontend build.
  - `start.sh` — uvicorn (port 8000) + vite dev (port 5173).
  - `scripts/dev.sh` — older combined install+start script (superseded by install/start).
  - GitHub Actions CI (`.github/workflows/ci.yml`) — pytest + vitest + build.
  - Golden-data test harness (`backend/tests/export_golden.py`, `test_golden.py`).

- **Reference material** (read-only, do not modify unless asked):
  - `Refs/PIDscope/` — Octave/MATLAB port of original PIDtoolbox.
  - `Refs/ScreenShotsShort/`, `Refs/ScreenShotsLong/` — original UI screenshots.
  - `Docs/pidtoolbox_react_clone_f16620bf.plan.md` — implementation plan.

### Fixed

- Step response indexing bug: FFT impulse response length mismatch with time vector caused `IndexError` in steady-state QC gate.
- Time-frequency spectrogram: variable segment lengths caused inhomogeneous numpy array; segments now padded to uniform length.
- Filter simulator API: numpy arrays in nested dicts failed JSON serialization; added `_to_json()` helper.
- Frontend build: Tailwind v4 `@apply` on custom classes removed; Plotly node polyfills added via `vite-plugin-node-polyfills`.
- LogViewer JSX syntax error after adding Save Settings button.

### Removed

- Docker packaging (`docker-compose.yml`, `docker/` directory) — project runs natively via `install.sh` / `start.sh`.

### Known gaps (for next agent)

- `blackbox_decode` not bundled; must be on PATH for `.BBL`/`.BFL` decode.
- Pure-Python BBL parser is a stub only (`bbl_native.py`).
- Golden tests use synthetic fixtures, not yet validated against Octave outputs from `Refs/PIDscope/tests/`.
- UI parity with original PIDtoolbox screenshots is approximate; many controls from original are missing (epoch drag-trim, period/markup tools, PID slider tool, multi-column freq×throttle grid, etc.).
- Chirp/Bode analysis exists as API endpoint only — no dedicated frontend page.
- `PSplotStats.m` full feature set not ported (only simplified stats module).
- No Playwright E2E tests.
- No Tauri desktop bundle.
- GPL-3.0 licensing not yet applied to this repo.
- Plan mentioned shadcn/ui; project uses plain Tailwind components instead.
