/* ============================================================
   山水智鉴 V0 — URL 状态同步 Hook
   将工作台状态同步到 URL 参数中
   ============================================================ */

import { useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useWorkbenchStore } from '@/app/store/workbench';

export function useUrlSync() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { selectedCandidateId, viewport } = useWorkbenchStore();

  // Sync state to URL
  const syncToUrl = useCallback(() => {
    setSearchParams((prev) => {
      if (selectedCandidateId) prev.set('candidate_id', selectedCandidateId);
      else prev.delete('candidate_id');

      prev.set('bbox', `${viewport.center[0].toFixed(4)},${viewport.center[1].toFixed(4)},${viewport.zoom.toFixed(1)}`);
      return prev;
    }, { replace: true });
  }, [selectedCandidateId, viewport, setSearchParams]);

  // Debounced sync
  useEffect(() => {
    const timer = setTimeout(syncToUrl, 500);
    return () => clearTimeout(timer);
  }, [syncToUrl]);

  // Restore from URL on mount
  useEffect(() => {
    const candidateId = searchParams.get('candidate_id');
    const bbox = searchParams.get('bbox');

    if (candidateId) {
      useWorkbenchStore.getState().setSelectedCandidateId(candidateId);
    }
    if (bbox) {
      const [lng, lat, zoom] = bbox.split(',').map(Number);
      if (!isNaN(lng) && !isNaN(lat)) {
        useWorkbenchStore.getState().setViewport({
          center: [lng, lat],
          zoom: zoom || 12,
        });
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
