import { getPlotLayoutBase, type AppTheme } from '../lib/constants';
import { useSessionStore } from '../store/sessionStore';

export function useAppTheme(): AppTheme {
  return useSessionStore((s) => s.settings.theme);
}

export function usePlotLayoutBase() {
  const theme = useAppTheme();
  return getPlotLayoutBase(theme);
}
