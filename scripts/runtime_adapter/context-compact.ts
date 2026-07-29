export interface ContextClient {
  session: {
    compact(input: { sessionID: string }): Promise<unknown>
    context(input: { sessionID: string }): Promise<{ data?: unknown[] }>
  }
}

export interface ContextPolicy {
  softMessages: number
  hardMessages: number
}

/**
 * Invoke OpenCode's native compaction instead of resending the append-only
 * history. The durable event log remains queryable; only the active model view
 * is condensed.
 */
export async function compactIfNeeded(
  client: ContextClient,
  sessionID: string,
  policy: ContextPolicy,
): Promise<{ action: "none" | "compact"; activeMessages: number }> {
  const before = await client.session.context({ sessionID })
  const activeMessages = before.data?.length ?? 0
  if (activeMessages < policy.softMessages) {
    return { action: "none", activeMessages }
  }
  await client.session.compact({ sessionID })
  const after = await client.session.context({ sessionID })
  const remaining = after.data?.length ?? 0
  if (activeMessages >= policy.hardMessages && remaining >= activeMessages) {
    throw new Error("native compaction did not reduce the active context view")
  }
  return { action: "compact", activeMessages: remaining }
}

