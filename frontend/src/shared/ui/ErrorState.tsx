/* ============================================================
   山水智鉴 V0 — Error State 组件
   ============================================================ */

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = '加载失败', onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-lg" style={{ gap: 'var(--spacing-md)' }}>
      <span style={{ color: 'var(--color-error)', fontSize: 'var(--font-size-sm)' }}>
        {message}
      </span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: 'var(--spacing-xs) var(--spacing-md)',
            fontSize: 'var(--font-size-sm)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-surface)',
            cursor: 'pointer',
          }}
        >
          重试
        </button>
      )}
    </div>
  );
}
