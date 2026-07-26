/* ============================================================
   山水智鉴 V0 — 应用入口
   ============================================================ */

import { RouterProvider } from 'react-router-dom';
import { router } from './router';

export default function App() {
  return <RouterProvider router={router} />;
}
