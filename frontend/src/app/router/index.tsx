/* ============================================================
   山水智鉴 V0 — 路由配置
   ============================================================ */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import AppLayout from './AppLayout';

const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const WorkbenchPage = lazy(() => import('@/pages/WorkbenchPage'));
const EventCenterPage = lazy(() => import('@/pages/EventCenterPage'));
const RunCenterPage = lazy(() => import('@/pages/RunCenterPage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));

function LazyPage({ Component }: { Component: React.LazyExoticComponent<React.ComponentType> }) {
  return (
    <Suspense fallback={<div className="flex flex-1 items-center justify-center p-lg"><span className="text-muted">加载中...</span></div>}>
      <Component />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        path: 'dashboard',
        element: <LazyPage Component={DashboardPage} />,
      },
      {
        index: true,
        element: <LazyPage Component={WorkbenchPage} />,
      },
      {
        path: 'events',
        element: <LazyPage Component={EventCenterPage} />,
      },
      {
        path: 'runs',
        element: <LazyPage Component={RunCenterPage} />,
      },
      {
        path: 'settings',
        element: <LazyPage Component={SettingsPage} />,
      },
      {
        path: '*',
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);
