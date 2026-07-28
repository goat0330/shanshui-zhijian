/* ============================================================
   山水智鉴 V0 — Run 详情
   ============================================================ */

import type { RunDTO } from '@/shared/types';

interface RunDetailProps {
  run: RunDTO;
}

export default function RunDetail({ run }: RunDetailProps) {
  return (
    <div style={{ padding: '0 var(--spacing-lg)' }}>
      <h4 style={{ marginBottom: 'var(--spacing-lg)' }}>{run.run_id}</h4>

      <div className="detail-section">
        <h5 className="detail-section-title">运行参数</h5>
        <div className="detail-meta-grid">
          <div><span className="text-xs text-muted">Task ID</span><div className="text-sm">{run.task_id}</div></div>
          <div><span className="text-xs text-muted">Task Spec</span><div className="text-sm">{run.task_spec_ref}</div></div>
          <div><span className="text-xs text-muted">状态</span><div className="text-sm">{run.execution_status}</div></div>
          <div><span className="text-xs text-muted">Git 分支</span><div className="text-sm">{run.git_branch}</div></div>
          <div><span className="text-xs text-muted">Git Commit</span><div className="text-sm text-mono" style={{ fontSize: 'var(--font-size-xs)' }}>{run.git_commit.slice(0, 12)}...</div></div>
          <div><span className="text-xs text-muted">Git Dirty</span><div className="text-sm">{run.git_dirty ? '是' : '否'}</div></div>
          <div><span className="text-xs text-muted">开始</span><div className="text-sm">{new Date(run.started_at).toLocaleString('zh-CN')}</div></div>
          <div><span className="text-xs text-muted">结束</span><div className="text-sm">{run.finished_at ? new Date(run.finished_at).toLocaleString('zh-CN') : '-'}</div></div>
        </div>
      </div>

      <div className="detail-section">
        <h5 className="detail-section-title">输入资源</h5>
        {run.input_assets.map((asset) => (
          <div key={asset} className="text-sm" style={{ padding: '2px 0' }}>{asset}</div>
        ))}
        <div className="text-xs text-muted">数据来源: {run.metadata_sources.join(', ')}</div>
      </div>

      <div className="detail-section">
        <h5 className="detail-section-title">产出制品</h5>
        {run.output_artifacts.map((artifact) => (
          <div key={artifact.artifact_id} style={{
            padding: 'var(--spacing-sm)',
            border: '1px solid var(--color-border-light)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--spacing-xs)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="text-sm font-medium">{artifact.asset_type}</span>
              <span className="text-xs text-muted">{(artifact.size_bytes / 1024 / 1024).toFixed(1)} MB</span>
            </div>
            <div className="text-xs text-muted">{artifact.file_path}</div>
            <div className="text-xs text-muted">SHA256: {artifact.sha256.slice(0, 16)}...</div>
          </div>
        ))}
      </div>

      {run.failure_stage && (
        <div className="detail-section">
          <h5 className="detail-section-title">失败阶段</h5>
          <div style={{ color: 'var(--color-error)' }}>{run.failure_stage}</div>
        </div>
      )}
    </div>
  );
}
