import { useEffect, useMemo } from 'react';
import { EpochRangeSlider } from '../components/EpochRangeSlider';
import { FileDropzone } from '../components/FileDropzone';
import { TimeSeriesPlot } from '../components/TimeSeriesPlot';
import { TraceTogglePanel } from '../components/TraceTogglePanel';
import { api, type TraceData } from '../lib/api';
import { DEFAULT_TRACES } from '../lib/constants';
import { buildMotorPanelCaption, buildPanelCaption, computeTraceYRange } from '../lib/utils';
import { useSessionStore } from '../store/sessionStore';

type PanelTrace = TraceData['panels'][string][number];

function visiblePanelTraces(
  panel: TraceData['panels'][string] | undefined,
  visibleTraces: string[],
): PanelTrace[] {
  return panel?.filter((t) => visibleTraces.includes(t.key)) ?? [];
}

export function LogViewerPage() {
  const {
    sessionId, files, traceData, loading, error, parseWarnings, settings, visibleTraces,
    uploadFiles, refreshTraces, setSettings, setFirmware, toggleTrace,
    selectedFileIdx, setSelectedFile, setEpoch, reset, initSession,
    firmwareOptions,
  } = useSessionStore();

  useEffect(() => {
    if (!sessionId) {
      initSession();
    }
  }, [sessionId, initSession]);

  useEffect(() => {
    if (files.length > 0) refreshTraces();
  }, [settings.plotR, settings.plotP, settings.plotY, settings.lineSmooth, visibleTraces]);

  const available = traceData?.available_traces || [...DEFAULT_TRACES];

  const rollTraces = useMemo(
    () => visiblePanelTraces(traceData?.panels?.roll, visibleTraces),
    [traceData?.panels?.roll, visibleTraces],
  );
  const pitchTraces = useMemo(
    () => visiblePanelTraces(traceData?.panels?.pitch, visibleTraces),
    [traceData?.panels?.pitch, visibleTraces],
  );
  const yawTraces = useMemo(
    () => visiblePanelTraces(traceData?.panels?.yaw, visibleTraces),
    [traceData?.panels?.yaw, visibleTraces],
  );

  const rollYRange = useMemo(() => computeTraceYRange(rollTraces), [rollTraces]);
  const pitchYRange = useMemo(() => computeTraceYRange(pitchTraces), [pitchTraces]);
  const yawYRange = useMemo(() => computeTraceYRange(yawTraces), [yawTraces]);

  const rollCaption = useMemo(() => buildPanelCaption('roll', rollTraces), [rollTraces]);
  const pitchCaption = useMemo(() => buildPanelCaption('pitch', pitchTraces), [pitchTraces]);
  const yawCaption = useMemo(() => buildPanelCaption('yaw', yawTraces), [yawTraces]);

  const motorPanelTraces =
    traceData?.motor_panel?.filter((t) => visibleTraces.includes(t.key)) ?? [];
  const throttleTraces = motorPanelTraces.filter((t) => t.key === 'throttle');
  const motorRpmTraces = motorPanelTraces.filter((t) => t.key.startsWith('motor_'));
  const motorsUseRpm =
    traceData?.motor_panel_units?.motors === 'rpm' ||
    motorRpmTraces.some((t) => t.yaxis === 'y2');

  const motorsUnit: 'rpm' | 'percent' = motorsUseRpm ? 'rpm' : 'percent';
  const throttleCaption = useMemo(
    () => buildMotorPanelCaption(throttleTraces, motorsUnit),
    [throttleTraces, motorsUnit],
  );
  const motorRpmCaption = useMemo(
    () => buildMotorPanelCaption(motorRpmTraces, motorsUnit),
    [motorRpmTraces, motorsUnit],
  );
  const combinedMotorCaption = useMemo(
    () => buildMotorPanelCaption(motorPanelTraces, motorsUnit),
    [motorPanelTraces, motorsUnit],
  );

  return (
    <div className="flex flex-1 min-h-0 min-w-0 w-full gap-4">
      <TraceTogglePanel
        traces={available}
        visible={visibleTraces}
        onToggle={toggleTrace}
      />

      <div className="flex flex-1 flex-col min-h-0 min-w-0 gap-2">
        {files.length === 0 ? (
          <FileDropzone onFiles={uploadFiles} />
        ) : (
          <>
            {traceData?.full_time_range && traceData.epoch && (
              <div className="shrink-0">
                <EpochRangeSlider
                  min={traceData.full_time_range[0]}
                  max={traceData.full_time_range[1]}
                  start={traceData.epoch[0]}
                  end={traceData.epoch[1]}
                  onCommit={setEpoch}
                  disabled={loading}
                />
              </div>
            )}
            <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-2">
            {traceData?.panels?.roll && settings.plotR && rollTraces.length > 0 && (
              <TimeSeriesPlot
                title={rollCaption.title}
                traces={rollTraces}
                yLabel={rollCaption.yLabel}
                yRange={rollYRange}
                lineWidth={settings.lineWidth}
                saveFilename="log-viewer-roll"
              />
            )}
            {traceData?.panels?.pitch && settings.plotP && pitchTraces.length > 0 && (
              <TimeSeriesPlot
                title={pitchCaption.title}
                traces={pitchTraces}
                yLabel={pitchCaption.yLabel}
                yRange={pitchYRange}
                lineWidth={settings.lineWidth}
              />
            )}
            {traceData?.panels?.yaw && settings.plotY && yawTraces.length > 0 && (
              <TimeSeriesPlot
                title={yawCaption.title}
                traces={yawTraces}
                yLabel={yawCaption.yLabel}
                yRange={yawYRange}
                lineWidth={settings.lineWidth}
              />
            )}
            {motorPanelTraces.length > 0 && motorsUseRpm ? (
              <>
                {throttleTraces.length > 0 && (
                  <TimeSeriesPlot
                    title={throttleCaption.title}
                    traces={throttleTraces}
                    yLabel={throttleCaption.yLabel}
                    yRange={[0, 100]}
                    lineWidth={settings.lineWidth}
                  />
                )}
                {motorRpmTraces.length > 0 && (
                  <TimeSeriesPlot
                    title={motorRpmCaption.title}
                    traces={motorRpmTraces}
                    yLabel={motorRpmCaption.yLabel}
                    lineWidth={settings.lineWidth}
                  />
                )}
              </>
            ) : motorPanelTraces.length > 0 ? (
              <TimeSeriesPlot
                title={combinedMotorCaption.title}
                traces={motorPanelTraces}
                yLabel={combinedMotorCaption.yLabel}
                yRange={[0, 100]}
                lineWidth={settings.lineWidth}
              />
            ) : null}
            </div>
          </>
        )}
        {loading && <p className="text-sm text-blue-400 shrink-0">Loading...</p>}
        {error && <p className="text-sm text-red-400 shrink-0">{error}</p>}
        {parseWarnings.length > 0 && (
          <div className="text-sm text-amber-400 shrink-0 space-y-1">
            <p className="font-medium">Some log data was not available in this file:</p>
            <ul className="list-disc list-inside text-xs space-y-0.5">
              {parseWarnings.map((msg) => (
                <li key={msg}>{msg}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="panel w-56 shrink-0 space-y-3">
        <h3 className="text-sm font-semibold">Control Panel</h3>
        <select
          className="select-input"
          value={settings.firmware}
          onChange={(e) => void setFirmware(e.target.value)}
        >
          {firmwareOptions.map((fw) => (
            <option key={fw.key} value={fw.key}>
              {fw.display_name}
            </option>
          ))}
        </select>

        <FileDropzone onFiles={uploadFiles} label="Open File" />

        <button className="btn-reset w-full" onClick={reset}>Reset</button>

        {files.length > 0 && (
          <select
            className="select-input"
            value={selectedFileIdx}
            onChange={(e) => setSelectedFile(Number(e.target.value))}
          >
            {files.map((f, i) => (
              <option key={f.file_id} value={i}>{f.original_name}</option>
            ))}
          </select>
        )}

        <div className="flex gap-2">
          {(['plotR', 'plotP', 'plotY'] as const).map((k, i) => (
            <label key={k} className="text-sm">
              <input
                type="checkbox"
                checked={settings[k]}
                onChange={(e) => setSettings({ [k]: e.target.checked })}
              />{' '}
              {['X', 'Y', 'Z'][i]}
            </label>
          ))}
        </div>

        <select
          className="select-input"
          value={settings.lineSmooth}
          onChange={(e) => setSettings({ lineSmooth: Number(e.target.value) })}
        >
          <option value={1}>line smooth off</option>
          <option value={2}>line smooth low</option>
          <option value={3}>line smooth med</option>
          <option value={4}>line smooth high</option>
        </select>

        <select
          className="select-input"
          value={settings.lineWidth}
          onChange={(e) => setSettings({ lineWidth: Number(e.target.value) })}
        >
          {[1, 2, 3, 4, 5].map((w) => (
            <option key={w} value={w}>line width {w}</option>
          ))}
        </select>

        <select
          className="select-input"
          value={settings.theme}
          onChange={(e) => setSettings({ theme: e.target.value as 'dark' | 'light' })}
        >
          <option value="dark">Dark Theme</option>
          <option value="light">Light Theme</option>
        </select>

        <button
          className="btn-run w-full text-sm"
          onClick={() => api.saveSettings(settings as unknown as Record<string, unknown>)}
        >
          Save Settings
        </button>

        {traceData?.metadata && (
          <div className="text-xs text-[var(--text-secondary)] space-y-1 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
            <p>{String(traceData.metadata.fw_type)}</p>
            <p>Rate: {traceData.lograte_khz} kHz</p>
            <p>Epoch: {traceData.epoch?.join(' – ')} s</p>
          </div>
        )}
      </div>
    </div>
  );
}
