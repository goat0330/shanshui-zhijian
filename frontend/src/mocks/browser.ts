/* ============================================================
   山水智鉴 V0 — MSW Browser Worker
   ============================================================ */

import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
