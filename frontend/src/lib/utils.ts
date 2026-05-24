/** Save Plotly figure as PNG using browser download */
export async function savePlotlyFigure(plotElement: HTMLElement, filename: string) {
  const Plotly = await import('plotly.js');
  await Plotly.downloadImage(plotElement, {
    format: 'png',
    width: 1920,
    height: 1080,
    filename: filename.replace(/\.[^.]+$/, ''),
  });
}

/** Keyboard shortcut handler */
export function useKeyboardShortcuts(handlers: Record<string, () => void>) {
  if (typeof window === 'undefined') return;

  const onKey = (e: KeyboardEvent) => {
    const key = `${e.ctrlKey || e.metaKey ? 'ctrl+' : ''}${e.key.toLowerCase()}`;
    if (handlers[key]) {
      e.preventDefault();
      handlers[key]();
    }
  };

  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}
