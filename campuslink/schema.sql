PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS institutions (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE
);
INSERT OR IGNORE INTO institutions VALUES ('zut', 'Zambia University College of Technology');
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 username TEXT NOT NULL UNIQUE COLLATE NOCASE, display_name TEXT NOT NULL,
 password_hash TEXT NOT NULL, dob TEXT, bio TEXT NOT NULL DEFAULT '',
 institution_id TEXT NOT NULL DEFAULT 'zut' REFERENCES institutions(id),
 program TEXT NOT NULL DEFAULT '', year INTEGER NOT NULL DEFAULT 1 CHECK(year BETWEEN 1 AND 7),
 subjects TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '', study_goals TEXT NOT NULL DEFAULT '',
 discoverable INTEGER NOT NULL DEFAULT 1, friend_goal INTEGER NOT NULL DEFAULT 1,
 study_goal INTEGER NOT NULL DEFAULT 1, dating_enabled INTEGER NOT NULL DEFAULT 0,
 gender TEXT NOT NULL DEFAULT '', dating_genders TEXT NOT NULL DEFAULT '[]',
 dating_min INTEGER NOT NULL DEFAULT 18, dating_max INTEGER NOT NULL DEFAULT 100,
 onboarding_step INTEGER NOT NULL DEFAULT 0, notifications_enabled INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','deactivated','suspended')),
 role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student','moderator')),
 local_test INTEGER NOT NULL DEFAULT 0, adult_test INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS interests (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS user_interests (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 interest_id INTEGER NOT NULL REFERENCES interests(id), PRIMARY KEY(user_id, interest_id)
);
CREATE TABLE IF NOT EXISTS profile_photos (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 image BLOB NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
 position INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1,
 upload_key TEXT NOT NULL, upload_hash TEXT NOT NULL,
 operation_key TEXT, operation_hash TEXT,
 created_at INTEGER NOT NULL, UNIQUE(user_id, upload_key)
);
CREATE INDEX IF NOT EXISTS profile_photos_owner ON profile_photos(user_id, position, id);
CREATE TABLE IF NOT EXISTS profile_prompts (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 prompt_id TEXT NOT NULL, answer TEXT NOT NULL CHECK(length(answer) BETWEEN 1 AND 280),
 position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 2),
 PRIMARY KEY(user_id, prompt_id), UNIQUE(user_id, position)
);
CREATE TABLE IF NOT EXISTS dating_intentions (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 intention TEXT NOT NULL CHECK(intention IN ('relationship','getting_to_know','figuring_out')),
 displayed INTEGER NOT NULL DEFAULT 0 CHECK(displayed IN (0,1))
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf TEXT NOT NULL, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS recovery_tokens (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
 blocker TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 blocked TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 PRIMARY KEY(blocker, blocked), CHECK(blocker != blocked)
);
CREATE TABLE IF NOT EXISTS relationships (
 id TEXT PRIMARY KEY, low_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 high_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('friend','study','dating')),
 sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 status TEXT NOT NULL CHECK(status IN ('pending','accepted','declined','cancelled','removed')),
 updated_at INTEGER NOT NULL, created_at INTEGER NOT NULL,
 UNIQUE(low_id, high_id, kind), CHECK(low_id < high_id)
);
CREATE TABLE IF NOT EXISTS dating_likes (
 sender TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 target TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 PRIMARY KEY(sender, target), CHECK(sender != target)
);
CREATE TABLE IF NOT EXISTS dismissals (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 target TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, until_at INTEGER NOT NULL, PRIMARY KEY(user_id, target, kind)
);
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 relationship_id TEXT NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
 sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 client_id TEXT NOT NULL, body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 4000),
 created_at INTEGER NOT NULL, UNIQUE(relationship_id, sender_id, client_id)
);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(relationship_id, id);
CREATE TABLE IF NOT EXISTS read_cursors (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 relationship_id TEXT NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
 message_id INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, relationship_id)
);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 body TEXT NOT NULL, relationship_id TEXT REFERENCES relationships(id) ON DELETE CASCADE,
 read INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS events_user ON events(user_id, id);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, reporter TEXT REFERENCES users(id) ON DELETE SET NULL,
 target TEXT REFERENCES users(id) ON DELETE SET NULL,
 message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
 reason TEXT NOT NULL, detail TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS moderation_audit (
 id INTEGER PRIMARY KEY, moderator TEXT REFERENCES users(id) ON DELETE SET NULL,
 report_id TEXT NOT NULL REFERENCES reports(id), action TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits (
 key TEXT PRIMARY KEY, window INTEGER NOT NULL, count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS delivery_cursors (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 relationship_id TEXT NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
 message_id INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, relationship_id)
);
CREATE TABLE IF NOT EXISTS profile_likes (
 sender TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 target TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL, PRIMARY KEY(sender,target), CHECK(sender != target)
);
CREATE TABLE IF NOT EXISTS post_photos (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 image BLOB NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
 upload_key TEXT NOT NULL, upload_hash TEXT NOT NULL, created_at INTEGER NOT NULL,
 UNIQUE(user_id,upload_key)
);
CREATE TABLE IF NOT EXISTS posts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 client_id TEXT NOT NULL, body TEXT NOT NULL CHECK(length(body)<=2000),
 photo_id TEXT UNIQUE REFERENCES post_photos(id) ON DELETE SET NULL,
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, UNIQUE(user_id,client_id)
);
CREATE INDEX IF NOT EXISTS posts_author ON posts(user_id,id);
CREATE TABLE IF NOT EXISTS post_likes (
 post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL, PRIMARY KEY(post_id,user_id)
);
CREATE TABLE IF NOT EXISTS message_requests (
 id TEXT PRIMARY KEY, sender TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 target TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 1000),
 kind TEXT NOT NULL CHECK(kind IN ('friend','study','dating')),
 post_id INTEGER REFERENCES posts(id) ON DELETE SET NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined')),
 relationship_id TEXT REFERENCES relationships(id) ON DELETE SET NULL,
 client_id TEXT NOT NULL, created_at INTEGER NOT NULL,
 UNIQUE(sender,target), CHECK(sender != target)
);
CREATE TABLE IF NOT EXISTS operator_roles (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 granted_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 target_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS operation_runs (
 operation TEXT PRIMARY KEY, status TEXT NOT NULL,
 started_at INTEGER NOT NULL, completed_at INTEGER,
 summary TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS pilot_feedback (
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 category TEXT NOT NULL CHECK(category IN ('bug','usability','suggestion')),
 body TEXT NOT NULL CHECK(length(body) BETWEEN 10 AND 2000),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','triaged','resolved')),
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS email_verification_tokens (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 email_hash TEXT NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS account_verification (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 email_hash TEXT NOT NULL, email_verified_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS eligibility_checks (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('student','adult')),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 method TEXT NOT NULL DEFAULT '', reference_hash TEXT NOT NULL DEFAULT '',
 expires_at INTEGER, updated_at INTEGER NOT NULL,
 PRIMARY KEY(user_id,kind)
);
CREATE TABLE IF NOT EXISTS mail_outbox (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 purpose TEXT NOT NULL CHECK(purpose IN ('recovery','verify_email')),
 email_hash TEXT NOT NULL, key_id TEXT NOT NULL,
 created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','sending','sent','used','cancelled','failed')),
 attempts INTEGER NOT NULL DEFAULT 0, next_attempt INTEGER NOT NULL,
 lease_until INTEGER NOT NULL DEFAULT 0, sent_at INTEGER,
 last_error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS mail_outbox_due ON mail_outbox(status,next_attempt,lease_until);
CREATE TABLE IF NOT EXISTS membership_approvals (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
 reason TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS service_state (
 key TEXT PRIMARY KEY, value TEXT NOT NULL
);
INSERT OR IGNORE INTO service_state(key,value) SELECT 'membership_approval_activated','1' WHERE EXISTS(SELECT 1 FROM operator_roles);
INSERT OR IGNORE INTO membership_approvals(user_id,updated_at) SELECT id,created_at FROM users;
CREATE TRIGGER IF NOT EXISTS new_account_membership AFTER INSERT ON users
BEGIN
 INSERT OR IGNORE INTO membership_approvals(user_id,updated_at) VALUES (NEW.id,NEW.created_at);
END;
CREATE TABLE IF NOT EXISTS provider_attempts (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('student','adult')),
 program_id TEXT NOT NULL, provider_id TEXT UNIQUE,
 status TEXT NOT NULL CHECK(status IN ('creating','pending','approved','rejected','failed')),
 email_hash TEXT NOT NULL, identity_hash TEXT NOT NULL DEFAULT '',
 live_started INTEGER NOT NULL DEFAULT 0,
 consent_version TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS provider_attempts_owner ON provider_attempts(user_id,kind,created_at);
CREATE TABLE IF NOT EXISTS provider_events (
 body_sha256 TEXT PRIMARY KEY, received_at INTEGER NOT NULL
);
PRAGMA user_version = 6;
