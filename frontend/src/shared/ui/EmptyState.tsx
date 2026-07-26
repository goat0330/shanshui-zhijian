/* ============================================================
   山水智鉴 V0 — Empty State 组件
   ============================================================ */

interface EmptyStateProps {
  message?: string;
  icon?: string;
}

export function EmptyState({ message = '暂无数据', icon = '📭' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-lg" style={{ gap: 'var(--spacing-sm)', padding: 'var(--spacing-xxl)' }}>
      <span style={{ fontSize: 24 }}>{icon}</span>
      <span className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>{message}</span>
    </div>
  );
}
