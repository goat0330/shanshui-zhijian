/**
 * Additive Ensemble migration. Keep legacy session columns as compatibility
 * mirrors until all lookups use actor.active_session_id.
 */
export const ACTOR_IDENTITY_MIGRATION = `
CREATE TABLE IF NOT EXISTS actor (
  id TEXT PRIMARY KEY,
  team_id TEXT NOT NULL REFERENCES team(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('lead','member')),
  active_session_id TEXT NOT NULL,
  session_epoch INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK(status IN ('active','retired')),
  time_created INTEGER NOT NULL,
  time_updated INTEGER NOT NULL,
  UNIQUE(team_id,name)
);
CREATE INDEX IF NOT EXISTS actor_active_session_idx
  ON actor(active_session_id) WHERE status='active';

CREATE TABLE IF NOT EXISTS actor_session_epoch (
  id TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL REFERENCES actor(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('active','retired')),
  handoff_ref TEXT,
  time_created INTEGER NOT NULL,
  time_retired INTEGER,
  UNIQUE(actor_id,epoch),
  UNIQUE(actor_id,session_id)
);
CREATE INDEX IF NOT EXISTS actor_epoch_active_idx
  ON actor_session_epoch(actor_id,state);

ALTER TABLE team ADD COLUMN lead_actor_id TEXT;
ALTER TABLE team_member ADD COLUMN actor_id TEXT;
`;

