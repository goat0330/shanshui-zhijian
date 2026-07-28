/* ============================================================
    山水智鉴 V0 — 应用布局
   ============================================================ */

import { Outlet, NavLink } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/app/providers/queryClient';
import DataSourceBadge from '@/shared/ui/DataSourceBadge';
import './AppLayout.css';

const navItems = [
  { path: '/dashboard', label: '驾驶舱' },
  { path: '/workbench', label: '研判工作台' },
  { path: '/events', label: '事件中心' },
  { path: '/runs', label: '运行记录' },
  { path: '/settings', label: '系统设置' },
];

export default function AppLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="app-layout">
        <header className="app-header">
          <div className="app-header-left">
            <span className="app-logo">山水智鉴</span>
            <span className="app-version">V0</span>
          </div>
          <nav className="app-nav">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/workbench'}
                className={({ isActive }) =>
                  `app-nav-item ${isActive ? 'app-nav-item--active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="app-header-right">
            <DataSourceBadge mode="MOCK" />
          </div>
        </header>
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </QueryClientProvider>
  );
}
