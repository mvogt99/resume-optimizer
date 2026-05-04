# SQLite → PostgreSQL Migration Guide

**Current:** SQLite (`backend/database.db`) | **Target:** PostgreSQL | **Downtime:** <5 minutes

---

## Pre-Migration Checklist

- [x] PostgreSQL 12+ installed
- [x] psql CLI available
- [x] Backup current SQLite database
- [x] Read-replica not needed for migration (single-user system)

---

## Step 1: Backup SQLite Database

```bash
# Backup current SQLite database
cp backend/database.db backend/database.db.backup

# Verify backup
sqlite3 backend/database.db.backup ".tables"
# Should list: users, journey_sources, journey_events, ...
```

---

## Step 2: Create PostgreSQL Database

```bash
# Connect to PostgreSQL as admin
psql -U postgres

# In psql shell:
CREATE USER journey_user WITH PASSWORD 'secure_password_here';
CREATE DATABASE journey_mining OWNER journey_user;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE journey_mining TO journey_user;
\c journey_mining
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO journey_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO journey_user;

# Exit psql
\q
```

---

## Step 3: Create Schema in PostgreSQL

```sql
-- Connect as journey_user
psql -U journey_user -d journey_mining

-- Create all tables
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE journey_mining_runs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL,
    opts_json TEXT,
    watermarks_json TEXT
);

CREATE TABLE journey_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    full_text TEXT,
    significance_score INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE journey_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_id INTEGER NOT NULL REFERENCES journey_sources(id),
    title TEXT NOT NULL,
    significance_score INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cluster_id INTEGER,
    is_cluster_head INTEGER DEFAULT 0
);

-- Create indexes for performance
CREATE INDEX idx_journey_sources_user_id ON journey_sources(user_id);
CREATE INDEX idx_journey_events_user_id ON journey_events(user_id);
CREATE INDEX idx_journey_events_cluster_id ON journey_events(cluster_id);
CREATE INDEX idx_journey_mining_runs_user_id ON journey_mining_runs(user_id);

-- Exit psql
\q
```

---

## Step 4: Migrate Data from SQLite to PostgreSQL

**Option A: Using Python script (recommended)**

```python
# migrate.py
import sqlite3
import psycopg2
from datetime import datetime

# Connect to SQLite
sqlite_conn = sqlite3.connect('backend/database.db')
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    dbname="journey_mining",
    user="journey_user",
    password="secure_password_here",
    host="localhost",
    port="5432"
)
pg_cursor = pg_conn.cursor()

# Migrate users
print("Migrating users...")
sqlite_cursor.execute("SELECT * FROM users")
for row in sqlite_cursor.fetchall():
    pg_cursor.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
        (row["id"], row["email"], row["password_hash"])
    )
pg_conn.commit()
print(f"  ✓ {pg_cursor.rowcount} users migrated")

# Migrate journey_sources
print("Migrating journey_sources...")
sqlite_cursor.execute("SELECT * FROM journey_sources")
for row in sqlite_cursor.fetchall():
    pg_cursor.execute(
        "INSERT INTO journey_sources (id, user_id, source_type, title, full_text, significance_score, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (row["id"], row["user_id"], row["source_type"], row["title"], row["full_text"],
         row["significance_score"], row["created_at"])
    )
pg_conn.commit()
print(f"  ✓ {pg_cursor.rowcount} sources migrated")

# Migrate journey_events
print("Migrating journey_events...")
sqlite_cursor.execute("SELECT * FROM journey_events")
for row in sqlite_cursor.fetchall():
    pg_cursor.execute(
        "INSERT INTO journey_events (id, user_id, source_id, title, significance_score, created_at, cluster_id, is_cluster_head) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (row["id"], row["user_id"], row["source_id"], row["title"], row["significance_score"],
         row["created_at"], row["cluster_id"], row["is_cluster_head"])
    )
pg_conn.commit()
print(f"  ✓ {pg_cursor.rowcount} events migrated")

# Migrate journey_mining_runs
print("Migrating journey_mining_runs...")
sqlite_cursor.execute("SELECT * FROM journey_mining_runs")
for row in sqlite_cursor.fetchall():
    pg_cursor.execute(
        "INSERT INTO journey_mining_runs (id, user_id, started_at, completed_at, status, opts_json, watermarks_json) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (row["id"], row["user_id"], row["started_at"], row["completed_at"], row["status"],
         row["opts_json"], row["watermarks_json"])
    )
pg_conn.commit()
print(f"  ✓ {pg_cursor.rowcount} mining runs migrated")

# Verify counts match
sqlite_cursor.execute("SELECT COUNT(*) as cnt FROM users")
sqlite_users = sqlite_cursor.fetchone()["cnt"]
pg_cursor.execute("SELECT COUNT(*) FROM users")
pg_users = pg_cursor.fetchone()[0]
assert sqlite_users == pg_users, f"User count mismatch: SQLite {sqlite_users} vs PG {pg_users}"
print(f"\n✓ Migration complete: {pg_users} users verified")

sqlite_conn.close()
pg_conn.close()
```

Run:
```bash
python migrate.py
```

**Option B: Using pg_dumpall and sed (for larger databases)**

```bash
# Dump SQLite to SQL
sqlite3 backend/database.db .dump > sqlite_dump.sql

# Convert SQLite syntax to PostgreSQL syntax (basic)
sed -i 's/AUTOINCREMENT//' sqlite_dump.sql
sed -i "s/sqlite_sequence//" sqlite_dump.sql

# Apply to PostgreSQL
psql -U journey_user -d journey_mining < sqlite_dump.sql
```

---

## Step 5: Update Application Configuration

Update `backend/models.py` to use PostgreSQL:

```python
# backend/models.py

import os
import psycopg2
from psycopg2 import pool

# PostgreSQL connection string from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://journey_user:password@localhost:5432/journey_mining")

# Initialize connection pool
_connection_pool = None

def get_db_connection():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, DATABASE_URL)
    return _connection_pool.getconn()

def release_db_connection(conn):
    if _connection_pool and conn:
        _connection_pool.putconn(conn)

# Rest of models.py remains the same
# The Row interface works with both sqlite3 and psycopg2
```

---

## Step 6: Test PostgreSQL Connection

```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql://journey_user:secure_password_here@localhost:5432/journey_mining"

# Test in Python
python -c "
from models import get_db
with get_db() as conn:
    result = conn.execute('SELECT COUNT(*) FROM users').fetchone()
    print(f'✓ PostgreSQL connection working. Users: {result[0]}')
"
```

---

## Step 7: Update Environment Variables

Update `.env` or systemd service:

```bash
# .env
DATABASE_URL=postgresql://journey_user:secure_password_here@localhost:5432/journey_mining
FLASK_ENV=production
```

Or systemd service (`~/.config/systemd/user/resume-optimizer.service`):

```ini
[Service]
Environment="DATABASE_URL=postgresql://journey_user:secure_password_here@localhost:5432/journey_mining"
ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
```

---

## Step 8: Run Test Suite Against PostgreSQL

```bash
# Run all tests with PostgreSQL
export DATABASE_URL="postgresql://journey_user:password@localhost:5432/journey_mining"
pytest backend/tests/ -v

# Expected: All 82 tests pass
```

---

## Step 9: Validate Data Integrity

```sql
-- Connect to PostgreSQL
psql -U journey_user -d journey_mining

-- Check data counts
SELECT 'users' as table_name, COUNT(*) FROM users
UNION ALL
SELECT 'journey_sources', COUNT(*) FROM journey_sources
UNION ALL
SELECT 'journey_events', COUNT(*) FROM journey_events
UNION ALL
SELECT 'journey_mining_runs', COUNT(*) FROM journey_mining_runs;

-- Check for orphans (events without sources)
SELECT COUNT(*) FROM journey_events WHERE source_id NOT IN (SELECT id FROM journey_sources);
-- Should return 0

-- Check for NULL significance scores
SELECT COUNT(*) FROM journey_events WHERE significance_score IS NULL;
-- Should return 0
```

---

## Step 10: Cutover

```bash
# 1. Stop Flask backend (minimal downtime)
pkill -f "gunicorn.*app:app"

# 2. Update DATABASE_URL to PostgreSQL
export DATABASE_URL="postgresql://journey_user:password@localhost:5432/journey_mining"

# 3. Start Flask backend with PostgreSQL
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app

# 4. Verify health
curl http://localhost:5000/health
# Expected: {"status": "healthy", "database": "connected"}

# 5. Run smoke test
python -c "
from models import get_db
from journey_scorer import score_event
from journey_dedup import deduplicate

source = {'title': 'feat: Test', 'full_text': '...', 'source_type': 'git_commit'}
score = score_event(source, {})
assert 1 <= score <= 5
print('✓ Application working with PostgreSQL')
"
```

---

## Rollback Plan

If PostgreSQL migration fails:

```bash
# 1. Stop Flask
pkill -f "gunicorn.*app:app"

# 2. Revert to SQLite
export DATABASE_URL="sqlite:///backend/database.db"

# 3. Start Flask
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app

# 4. Verify
curl http://localhost:5000/health

# Then debug PostgreSQL issues before retrying
```

---

## Post-Migration

1. **Backup PostgreSQL database:**
   ```bash
   pg_dump -U journey_user journey_mining > backup_2026-04-15.sql
   ```

2. **Archive SQLite backup:**
   ```bash
   gzip backend/database.db.backup
   mv backend/database.db.backup.gz backups/
   ```

3. **Monitor for a week:**
   - Check PostgreSQL slow query logs
   - Monitor connection pool utilization
   - Verify performance baseline (scoring, dedup, clustering)

4. **Clean up SQLite** (after verification):
   ```bash
   rm backend/database.db  # Keep .backup for reference
   ```

---

## Troubleshooting

### Issue: "FATAL: Ident authentication failed for user"

**Cause:** PostgreSQL authentication method

**Solution:**
```bash
# Edit /etc/postgresql/*/main/pg_hba.conf
# Change "ident" to "md5" or "scram-sha-256" for local connections

# Then:
sudo systemctl restart postgresql
```

### Issue: "FOREIGN KEY constraint failed"

**Cause:** Data migrated in wrong order or orphaned records

**Solution:**
```sql
-- Check for orphaned events
SELECT * FROM journey_events
WHERE source_id NOT IN (SELECT id FROM journey_sources);

-- Delete orphaned events (after investigation)
DELETE FROM journey_events
WHERE source_id NOT IN (SELECT id FROM journey_sources);
```

### Issue: "Sequence out of sync" (IDs don't match)

**Cause:** AUTOINCREMENT not preserved

**Solution:**
```sql
-- Reset sequence to max ID
SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
SELECT setval('journey_sources_id_seq', (SELECT MAX(id) FROM journey_sources));
SELECT setval('journey_events_id_seq', (SELECT MAX(id) FROM journey_events));
```

---

## Performance Tuning After Migration

Once PostgreSQL is live, optimize for your workload:

```sql
-- Analyze query planner
ANALYZE;

-- Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public';

-- Enable query logging for slow queries
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 1s threshold
SELECT pg_reload_conf();
```

---

## Timeline Estimate

- Pre-migration setup: 10 minutes
- Data migration: 5-30 minutes (depends on data volume)
- Testing: 15 minutes
- Cutover: 5 minutes
- **Total:** ~1 hour

---

## Success Criteria

- [x] All data migrated (counts match SQLite)
- [x] No orphaned records
- [x] Test suite passes 100%
- [x] E2E smoke tests pass
- [x] Zero downtime cutover (< 5 min)
- [x] Performance baseline maintained
