// ══════════════════════════════════════════════════════
//  Auto-generated TypeScript types from Workbench API
//  Source: openapi.json
//  Generated: 2026-07-26T01:47:10.907415
// ══════════════════════════════════════════════════════

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface ReviewRequest {
  action: string;
  category?: unknown;
  comment: string;
  evidence_refs?: string[];
  actor_ref?: string;
  base_version?: number;
}

export interface ValidationError {
  loc: unknown[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
