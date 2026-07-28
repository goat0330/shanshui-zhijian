/* ============================================================
   山水智鉴 V0 — Loading 组件
   ============================================================ */

export function Loading({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex flex-1 items-center justify-center p-lg">
      <span className="text-muted">{text}</span>
    </div>
  );
}
