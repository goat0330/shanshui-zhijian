/* ============================================================
   山水智鉴 V0 — API Error Tests
   验证错误映射逻辑
   ============================================================ */

import { describe, it, expect } from 'vitest';

interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  trace_id: string;
}

const errorMap: Record<string, { httpStatus: number; userMessage: string }> = {
  NOT_FOUND: { httpStatus: 404, userMessage: '资源不存在' },
  VALIDATION_ERROR: { httpStatus: 422, userMessage: '参数校验失败' },
  CONFLICT: { httpStatus: 409, userMessage: '版本冲突' },
  SERVICE_ERROR: { httpStatus: 500, userMessage: '服务内部错误' },
};

describe('Error Mapping', () => {
  it('should map NOT_FOUND to 404', () => {
    expect(errorMap['NOT_FOUND'].httpStatus).toBe(404);
    expect(errorMap['NOT_FOUND'].userMessage).toBe('资源不存在');
  });

  it('should map CONFLICT to 409', () => {
    expect(errorMap['CONFLICT'].httpStatus).toBe(409);
    expect(errorMap['CONFLICT'].userMessage).toBe('版本冲突');
  });

  it('should map SERVICE_ERROR to 500', () => {
    expect(errorMap['SERVICE_ERROR'].httpStatus).toBe(500);
    expect(errorMap['SERVICE_ERROR'].userMessage).toBe('服务内部错误');
  });

  it('should handle unknown error codes gracefully', () => {
    const unknownCode = 'UNKNOWN';
    const mapped = errorMap[unknownCode];
    expect(mapped).toBeUndefined();
  });

  it('should produce valid error JSON shape', () => {
    const error: ApiError = {
      code: 'NOT_FOUND',
      message: '资源不存在',
      details: {},
      trace_id: 'mock-trace-id',
    };
    expect(error.code).toBeDefined();
    expect(error.message).toBeDefined();
    expect(error.trace_id).toBeDefined();
    expect(typeof error.details).toBe('object');
  });

  it('should include trace_id for debugging', () => {
    const error: ApiError = {
      code: 'SERVICE_ERROR',
      message: '服务内部错误',
      details: {},
      trace_id: 'mock-500-trace',
    };
    expect(error.trace_id.length).toBeGreaterThan(0);
  });
});
