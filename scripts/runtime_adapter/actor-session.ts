import type { Database } from "./types"

export interface SessionClient {
  session: {
    get(input: { sessionID: string }): Promise<unknown>
  }
}

export interface RotateInput {
  actorID: string
  expectedSessionID: string
  newSessionID: string
  handoffRef?: string
}

/**
 * Rotate one durable Actor to a new ephemeral Session.
 *
 * Safety:
 * - verify the new Session through the OpenCode SDK;
 * - compare-and-swap the old Session and epoch;
 * - retire the previous epoch in the same transaction;
 * - mirror legacy team/team_member columns for old callers.
 */
export async function rotateActorSession(
  db: Database,
  client: SessionClient,
  input: RotateInput,
): Promise<{ actorID: string; epoch: number; sessionID: string }> {
  await client.session.get({ sessionID: input.newSessionID })
  const actor = db.query(
    `SELECT id,team_id,name,role,active_session_id,session_epoch
     FROM actor WHERE id=? AND status='active'`,
  ).get(input.actorID) as {
    id: string
    team_id: string
    name: string
    role: "lead" | "member"
    active_session_id: string
    session_epoch: number
  } | null
  if (!actor) throw new Error(`active actor not found: ${input.actorID}`)
  if (actor.active_session_id !== input.expectedSessionID) {
    throw new Error("session rotation rejected: stale expected session")
  }

  const nextEpoch = actor.session_epoch + 1
  const now = Date.now()
  db.transaction(() => {
    const changed = db.run(
      `UPDATE actor SET active_session_id=?,session_epoch=?,time_updated=?
       WHERE id=? AND active_session_id=? AND session_epoch=?`,
      input.newSessionID,
      nextEpoch,
      now,
      actor.id,
      input.expectedSessionID,
      actor.session_epoch,
    ).changes
    if (changed !== 1) throw new Error("session rotation lost compare-and-swap")
    db.run(
      `UPDATE actor_session_epoch
       SET state='retired',time_retired=?
       WHERE actor_id=? AND state='active'`,
      now,
      actor.id,
    )
    db.run(
      `INSERT INTO actor_session_epoch
       (id,actor_id,session_id,epoch,state,handoff_ref,time_created)
       VALUES (?,?,?,?,'active',?,?)`,
      `epoch_${actor.id}_${nextEpoch}`,
      actor.id,
      input.newSessionID,
      nextEpoch,
      input.handoffRef ?? null,
      now,
    )
    if (actor.role === "lead") {
      db.run(
        "UPDATE team SET lead_session_id=?,time_updated=? WHERE id=?",
        input.newSessionID,
        now,
        actor.team_id,
      )
    } else {
      db.run(
        `UPDATE team_member
         SET session_id=?,reported_to_lead=0,time_updated=?
         WHERE team_id=? AND actor_id=?`,
        input.newSessionID,
        now,
        actor.team_id,
        actor.id,
      )
    }
  })()
  return { actorID: actor.id, epoch: nextEpoch, sessionID: input.newSessionID }
}

/** Retired Sessions cannot resolve to a Team after actor migration. */
export function findActiveActorBySession(db: Database, sessionID: string) {
  return db.query(
    `SELECT a.id,a.team_id,a.name,a.role,t.name AS team_name
     FROM actor a JOIN team t ON t.id=a.team_id
     WHERE a.active_session_id=? AND a.status='active' AND t.status='active'`,
  ).all(sessionID)
}

