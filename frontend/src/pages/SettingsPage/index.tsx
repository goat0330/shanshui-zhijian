/* ============================================================
   山水智鉴 V0 — 系统设置
   ============================================================ */

import { useState } from 'react';
import config from '@/app/config';
import './index.css';

export default function SettingsPage() {
  const [currentMode] = useState(config.apiMode);

  return (
    <div className="page-container">
      <div className="page-header">
        <h3>系统设置</h3>
      </div>
      <div className="page-content settings-content">
        <section className="settings-section">
          <h4>API 模式</h4>
          <div className="settings-field">
            <span className="text-sm">当前模式：</span>
            <span className={`settings-badge settings-badge--${currentMode}`}>
              {currentMode === 'mock' ? 'Mock 数据' : 'Real API'}
            </span>
          </div>
          <p className="text-sm text-muted">
            Mode 切换通过环境变量 VITE_API_MODE 控制。当前为 {currentMode} 模式。
          </p>
        </section>

        <section className="settings-section">
          <h4>显示设置</h4>
          <div className="settings-field">
            <span className="text-sm">地图样式：</span>
            <span className="text-sm text-muted">{config.mapStyle}</span>
          </div>
          <div className="settings-field">
            <span className="text-sm">地图中心：</span>
            <span className="text-sm text-muted">{config.mapCenter.join(', ')}</span>
          </div>
          <div className="settings-field">
            <span className="text-sm">TiTiler：</span>
            <span className="text-sm text-muted">{config.titilerUrl}</span>
          </div>
        </section>

        <section className="settings-section">
          <h4>关于</h4>
          <p className="text-sm text-muted">
            山水智鉴 V0 — 面向河湖异常研判人员的多源水域异常感知与证据研判工作台。
          </p>
        </section>
      </div>
    </div>
  );
}
