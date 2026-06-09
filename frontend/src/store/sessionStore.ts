import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../lib/api';
import type { FileInfo, TraceData } from '../lib/api';
import {
  BETAFLIGHT_FAMILY_FIRMWARES,
  BLACKBOX_FILE_EXTENSIONS,
  FALLBACK_FIRMWARES,
  PX4_EXTRA_TRACES,
  type FirmwareOption,
} from '../lib/constants';

export interface AppSettings {
  firmware: string;
  theme: 'dark' | 'light';
  plotR: boolean;
  plotP: boolean;
  plotY: boolean;
  lineSmooth: number;
  lineWidth: number;
  singlePanel: boolean;
}

interface SessionState {
  sessionId: string | null;
  files: FileInfo[];
  selectedFileIdx: number;
  selectedLogIdx: number;
  traceData: TraceData | null;
  loading: boolean;
  error: string | null;
  parseWarnings: string[];
  settings: AppSettings;
  visibleTraces: string[];
  firmwareOptions: FirmwareOption[];

  setSettings: (s: Partial<AppSettings>) => void;
  loadFirmwares: () => Promise<void>;
  setFirmware: (firmware: string, force?: boolean) => Promise<void>;
  toggleTrace: (trace: string) => void;
  initSession: () => Promise<void>;
  restoreSession: () => Promise<void>;
  uploadFiles: (files: FileList) => Promise<void>;
  refreshTraces: () => Promise<void>;
  setSelectedFile: (idx: number) => void;
  setEpoch: (start: number, end: number) => Promise<void>;
  reset: () => void;
}

const DEFAULT_VISIBLE_TRACES = [
  'gyro', 'setpoint', 'pterm', 'iterm', 'dterm', 'throttle',
  'motor_0', 'motor_1', 'motor_2', 'motor_3',
];

function fileListHasUlg(files: FileList): boolean {
  return Array.from(files).some((f) => f.name.toLowerCase().endsWith('.ulg'));
}

function fileListHasBlackbox(files: FileList): boolean {
  return Array.from(files).some((f) => {
    const name = f.name.toLowerCase();
    return BLACKBOX_FILE_EXTENSIONS.some((ext) => name.endsWith(ext));
  });
}

function isBetaflightFamilyFirmware(firmware: string): boolean {
  return (BETAFLIGHT_FAMILY_FIRMWARES as readonly string[]).includes(firmware);
}

async function sessionFirmwareMatches(
  sessionId: string | null,
  firmware: string,
): Promise<boolean> {
  if (!sessionId) return false;
  try {
    const session = await api.getSession(sessionId);
    return session.firmware === firmware;
  } catch {
    return false;
  }
}

/** Drop trace series that are not currently visible (avoids stale overlays after toggles). */
function pruneTraceData(data: TraceData, visible: string[]): TraceData {
  const visibleSet = new Set(visible);
  const keep = <T extends { key: string }>(list: T[]) => list.filter((t) => visibleSet.has(t.key));
  return {
    ...data,
    panels: Object.fromEntries(
      Object.entries(data.panels).map(([panel, series]) => [panel, keep(series)]),
    ) as TraceData['panels'],
    motor_panel: keep(data.motor_panel ?? []),
  };
}

let traceRefreshId = 0;

/** Ensure the backend still has this session (in-memory; lost on server restart). */
async function ensureBackendSession(
  get: () => SessionState,
  set: (partial: Partial<SessionState> | ((s: SessionState) => Partial<SessionState>)) => void,
): Promise<string> {
  const { sessionId, settings } = get();
  if (sessionId) {
    try {
      await api.getSession(sessionId);
      return sessionId;
    } catch {
      // Stale ID from localStorage or server reload — create a new session below.
    }
  }
  const session = await api.createSession(settings.firmware);
  set({
    sessionId: session.session_id,
    files: [],
    traceData: null,
    selectedFileIdx: 0,
    selectedLogIdx: 0,
    error: null,
  });
  return session.session_id;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      sessionId: null,
      files: [],
      selectedFileIdx: 0,
      selectedLogIdx: 0,
      traceData: null,
      loading: false,
      error: null,
      parseWarnings: [],
      settings: {
        firmware: 'betaflight',
        theme: 'dark',
        plotR: true,
        plotP: true,
        plotY: true,
        lineSmooth: 1,
        lineWidth: 3,
        singlePanel: false,
      },
      visibleTraces: DEFAULT_VISIBLE_TRACES,
      firmwareOptions: FALLBACK_FIRMWARES,

      loadFirmwares: async () => {
        try {
          const list = await api.firmwares();
          if (list.length > 0) {
            set({ firmwareOptions: list });
          }
        } catch {
          // keep FALLBACK_FIRMWARES
        }
      },

      setFirmware: async (firmware, force = false) => {
        const { settings } = get();
        if (!force && settings.firmware === firmware) return;

        set({ loading: true, error: null });
        try {
          const session = await api.createSession(firmware);
          set({
            sessionId: session.session_id,
            settings: { ...settings, firmware },
            files: [],
            traceData: null,
            selectedFileIdx: 0,
            selectedLogIdx: 0,
            error: null,
          });
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      setSettings: (s) =>
        set((st) => {
          const settings = { ...st.settings, ...s };
          if (s.theme !== undefined) {
            document.body.className = s.theme;
          }
          return { settings };
        }),
      toggleTrace: (trace) =>
        set((st) => ({
          visibleTraces: st.visibleTraces.includes(trace)
            ? st.visibleTraces.filter((t) => t !== trace)
            : [...st.visibleTraces, trace],
        })),

      initSession: async () => {
        set({ loading: true, error: null });
        try {
          await ensureBackendSession(get, set);
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      restoreSession: async () => {
        set({ loading: true, error: null });
        try {
          const sessionId = await ensureBackendSession(get, set);
          const session = await api.getSession(sessionId);
          set({ files: session.files, error: null });
          if (session.files.length > 0) {
            await get().refreshTraces();
          }
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      uploadFiles: async (fileList) => {
        const { settings, sessionId } = get();

        if (fileListHasUlg(fileList)) {
          const needPx4 =
            settings.firmware !== 'px4' ||
            !(await sessionFirmwareMatches(sessionId, 'px4'));
          if (needPx4) {
            await get().setFirmware('px4', true);
          }
        } else if (fileListHasBlackbox(fileList)) {
          const needBetaflight =
            !isBetaflightFamilyFirmware(settings.firmware) ||
            !(await sessionFirmwareMatches(sessionId, settings.firmware));
          if (needBetaflight) {
            await get().setFirmware('betaflight', true);
          }
        }

        const files = Array.from(fileList);
        set({ loading: true, error: null, parseWarnings: [] });
        try {
          const sessionId = await ensureBackendSession(get, set);
          const warnings: string[] = [];
          for (const file of files) {
            const info = await api.uploadFile(sessionId, file);
            for (const msg of info.parse_warnings ?? []) {
              if (!warnings.includes(msg)) warnings.push(msg);
            }
          }
          const session = await api.getSession(sessionId);
          set({
            files: session.files,
            selectedFileIdx: session.files.length - 1,
            parseWarnings: warnings,
          });
          await get().refreshTraces();
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      refreshTraces: async () => {
        if (get().files.length === 0) return;

        let sessionId: string;
        try {
          sessionId = await ensureBackendSession(get, set);
        } catch (e) {
          set({ error: String(e) });
          return;
        }

        const { selectedFileIdx, selectedLogIdx, visibleTraces, settings, traceData } = get();

        const requestId = ++traceRefreshId;

        const axes: number[] = [];
        if (settings.plotR) axes.push(0);
        if (settings.plotP) axes.push(1);
        if (settings.plotY) axes.push(2);

        const prevAvailable = traceData?.available_traces;
        let tracesToRequest = prevAvailable
          ? visibleTraces.filter((t) => prevAvailable.includes(t))
          : [...new Set([
              ...visibleTraces,
              ...(settings.firmware === 'px4' ? PX4_EXTRA_TRACES : []),
            ])];

        set({ loading: true });
        try {
          const data = await api.getTraces(sessionId, {
            file_idx: selectedFileIdx,
            log_idx: selectedLogIdx,
            axes,
            traces: tracesToRequest,
            smooth_factor: settings.lineSmooth,
          });

          if (requestId !== traceRefreshId) return;

          const isPx4Trace = (t: string) =>
            (PX4_EXTRA_TRACES as readonly string[]).includes(t);
          const px4Available = data.available_traces.filter(isPx4Trace);
          const prevPx4Available = (prevAvailable ?? []).filter(isPx4Trace);
          // Auto-enable only when PX4 channels first appear (e.g. after ULG upload),
          // not when the user toggles them off (refreshTraces runs on visibleTraces change).
          const newlyAvailablePx4 = px4Available.filter(
            (t) => !prevPx4Available.includes(t),
          );
          const toEnable = newlyAvailablePx4.filter((t) => !visibleTraces.includes(t));
          const nextVisible =
            toEnable.length > 0 ? [...visibleTraces, ...toEnable] : visibleTraces;

          set({
            traceData: pruneTraceData(data, nextVisible),
            visibleTraces: nextVisible,
            error: null,
          });
        } catch (e) {
          if (requestId === traceRefreshId) {
            set({ error: String(e) });
          }
        } finally {
          if (requestId === traceRefreshId) {
            set({ loading: false });
          }
        }
      },

      setSelectedFile: (idx) => {
        set({ selectedFileIdx: idx, selectedLogIdx: 0 });
        get().refreshTraces();
      },

      setEpoch: async (start, end) => {
        if (get().files.length === 0) return;
        const sessionId = await ensureBackendSession(get, set);
        const { selectedFileIdx, selectedLogIdx } = get();
        await api.updateEpoch(sessionId, selectedFileIdx, selectedLogIdx, start, end);
        await get().refreshTraces();
      },

      reset: () =>
        set({
          files: [],
          traceData: null,
          selectedFileIdx: 0,
          selectedLogIdx: 0,
          error: null,
          parseWarnings: [],
        }),
    }),
    {
      name: 'pidbox-settings',
      partialize: (s) => ({
        settings: s.settings,
        visibleTraces: s.visibleTraces,
        // sessionId/files are ephemeral (backend in-memory); do not persist across reloads.
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.settings.theme) {
          document.body.className = state.settings.theme;
        }
      },
    },
  ),
);
