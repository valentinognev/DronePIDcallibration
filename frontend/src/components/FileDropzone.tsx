import { useCallback } from 'react';

interface Props {
  onFiles: (files: FileList) => void;
  accept?: string;
  label?: string;
}

export function FileDropzone({ onFiles, accept = '.bbl,.bfl,.csv,.bin,.json,.txt', label = 'Drop log files here or click to browse' }: Props) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
    },
    [onFiles],
  );

  return (
    <div
      className="panel border-dashed border-2 cursor-pointer text-center py-8 hover:border-blue-500 transition-colors"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = accept;
        input.onchange = () => input.files && onFiles(input.files);
        input.click();
      }}
    >
      <p className="text-[var(--text-secondary)]">{label}</p>
      <p className="text-xs mt-1 text-[var(--text-secondary)]">.BBL, .BFL, .CSV, .BIN, .JSON</p>
    </div>
  );
}
