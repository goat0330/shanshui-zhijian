export interface Statement {
  get(...params: unknown[]): unknown
  all(...params: unknown[]): unknown[]
}

export interface Database {
  query(sql: string): Statement
  run(sql: string, ...params: unknown[]): { changes: number }
  transaction<T>(fn: () => T): () => T
}

