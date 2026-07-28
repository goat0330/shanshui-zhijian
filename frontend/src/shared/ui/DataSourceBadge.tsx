import config from '@/app/config';

type DataSourceMode = 'MOCK' | 'FIXTURE' | 'REAL';

const modeColors: Record<DataSourceMode, string> = {
  MOCK: 'var(--color-warning)',
  FIXTURE: 'var(--color-info)',
  REAL: 'var(--color-event-confirmed)',
};

function DataSourceBadge({ mode }: { mode?: DataSourceMode }) {
  const current = mode ?? (config.apiMode === 'real' ? 'REAL' : 'MOCK');
  return (
    <span
      className="data-source-badge"
      style={{ backgroundColor: modeColors[current] }}
    >
      <span className="data-source-badge-dot" />
      {current}
    </span>
  );
}

export { DataSourceBadge };
export default DataSourceBadge;
