# Journey Mining: Operations Runbook

**For:** On-call engineers | **SLO:** 99.5% availability | **MTTR Target:** <15 min

---

## Quick Diagnostics

### Is the system healthy?

```bash
# 1. Check Flask backend
curl -s http://localhost:5000/health | jq .
# Expected: {"status": "healthy", "database": "connected"}

# 2. Check database connection
psql -U journey_user -d journey_mining -c "SELECT 1"
# Expected: 1 (no error)

# 3. Check recent logs
tail -20 /var/log/journey-mining.log
# Look for ERROR or FATAL

# 4. Quick test
python3 << 'EOF'
from models import get_db
with get_db() as conn:
    count = conn.execute("SELECT COUNT(*) FROM journey_events").fetchone()[0]
    print(f"✓ Database has {count} events")
EOF
```

### Is something slow?

```bash
# Check which process is consuming resources
top -u $(whoami) | head -20

# Check database query performance
psql -d journey_mining -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5"

# Monitor in real-time
watch -n 1 'ps aux | grep gunicorn'
```

---

## Common Issues & Solutions

### Issue: "Database connection refused"

**Symptoms:**
```
ERROR: FATAL: Ident authentication failed for user "journey_user"
```

**Diagnosis:**
```bash
# Check if PostgreSQL is running
systemctl status postgresql

# Check if database exists
psql -U postgres -l | grep journey_mining

# Try connecting directly
psql -U journey_user -h localhost -d journey_mining
```

**Solutions:**

1. **PostgreSQL not running:**
   ```bash
   systemctl start postgresql
   systemctl enable postgresql  # Auto-start on reboot
   ```

2. **Authentication method wrong:**
   ```bash
   # Edit /etc/postgresql/*/main/pg_hba.conf
   # Change "ident" to "md5" for user journey_user
   # Or add: local   journey_mining   journey_user   md5

   sudo systemctl restart postgresql
   ```

3. **User password wrong:**
   ```bash
   # Reset password
   psql -U postgres
   \password journey_user
   # Enter new password
   \q
   ```

---

### Issue: "Slow clustering (>5s for 1000 events)"

**Diagnosis:**
```bash
# Check database indexes
psql -d journey_mining -c "SELECT schemaname, tablename, indexname FROM pg_indexes WHERE schemaname='public'"

# Check table stats
psql -d journey_mining -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC"

# Analyze query plan
psql -d journey_mining -c "EXPLAIN ANALYZE SELECT * FROM journey_events WHERE user_id = 1"
```

**Solutions:**

1. **Missing indexes:**
   ```sql
   CREATE INDEX idx_journey_events_user_id ON journey_events(user_id);
   CREATE INDEX idx_journey_events_cluster_id ON journey_events(cluster_id);
   ```

2. **Table bloat (many deletes):**
   ```sql
   VACUUM ANALYZE journey_events;
   ```

3. **Query plan suboptimal:**
   ```sql
   -- Force index use if planner is wrong
   SET enable_seqscan = OFF;
   SELECT * FROM journey_events WHERE user_id = 1;
   ```

---

### Issue: "Out of disk space"

**Diagnosis:**
```bash
# Check disk usage
df -h

# Check largest tables
psql -d journey_mining -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables WHERE schemaname='public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"
```

**Solutions:**

1. **Archive old data:**
   ```sql
   -- Archive events older than 1 year
   CREATE TABLE journey_events_archive AS
   SELECT * FROM journey_events WHERE created_at < now() - interval '1 year';

   DELETE FROM journey_events WHERE created_at < now() - interval '1 year';
   VACUUM journey_events;
   ```

2. **Clean up temporary tables:**
   ```sql
   DROP TABLE IF EXISTS journey_events_temp;
   DROP TABLE IF EXISTS migration_scratch;
   VACUUM;
   ```

3. **Enable autovacuum (if disabled):**
   ```bash
   psql -c "ALTER SYSTEM SET autovacuum = ON"
   systemctl restart postgresql
   ```

---

### Issue: "High memory usage (Flask/Python)"

**Diagnosis:**
```bash
# Check process memory
ps aux | grep gunicorn | grep -v grep
# Look for VSZ (virtual) and RSS (resident) columns

# Check for memory leaks
python3 << 'EOF'
import gc
import sys
from models import get_db

# Force garbage collection
gc.collect()

# Run clustering 10 times, check memory growth
for i in range(10):
    with get_db() as conn:
        conn.execute("SELECT COUNT(*) FROM journey_events WHERE user_id = 1")
    if i % 5 == 0:
        print(f"Iteration {i}: OK")

print("✓ No obvious memory leak detected")
EOF
```

**Solutions:**

1. **Restart Flask (reclaim memory):**
   ```bash
   systemctl restart resume-optimizer  # or manually:
   pkill -f "gunicorn.*app:app"
   gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app &
   ```

2. **Increase available memory:**
   ```bash
   # Increase swap if running out of RAM
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

3. **Limit worker count:**
   ```bash
   # Reduce from 4 to 2 workers if memory is tight
   gunicorn -w 2 -b 0.0.0.0:5000 backend.app:app
   ```

---

### Issue: "Dedup failing with 'FOREIGN KEY constraint failed'"

**Symptoms:**
```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

**Root Cause:** Dedup tries to delete sources that events reference

**Solution:**

1. **Check which events are orphaned:**
   ```sql
   SELECT e.id, e.source_id FROM journey_events e
   WHERE e.source_id NOT IN (SELECT id FROM journey_sources);
   ```

2. **Option A: Delete orphaned events (if intentional):**
   ```sql
   DELETE FROM journey_events
   WHERE source_id NOT IN (SELECT id FROM journey_sources);
   ```

3. **Option B: Don't dedup if events reference sources:**
   ```python
   # In dedup logic, check first:
   with get_db() as conn:
       orphaned = conn.execute(
           "SELECT COUNT(*) FROM journey_events WHERE source_id NOT IN (SELECT id FROM journey_sources)"
       ).fetchone()[0]

   if orphaned > 0:
       print(f"⚠️ Cannot dedup: {orphaned} orphaned events exist")
       return None
   ```

---

## Monitoring & Alerts

### Setup Prometheus Metrics

```bash
# Install node_exporter for OS metrics
curl -OL https://github.com/prometheus/node_exporter/releases/download/v1.5.0/node_exporter-1.5.0.linux-amd64.tar.gz
tar xvfz node_exporter-1.5.0.linux-amd64.tar.gz
./node_exporter/node_exporter &

# Verify metrics endpoint
curl http://localhost:9100/metrics | head -20
```

### Key Metrics to Monitor

```bash
# Database size growth
psql -d journey_mining -c "SELECT pg_size_pretty(pg_database_size('journey_mining'))"

# Connection count
psql -d journey_mining -c "SELECT count(*) FROM pg_stat_activity"

# Long-running queries
psql -d journey_mining -c "
SELECT pid, usename, query, query_start FROM pg_stat_activity
WHERE query_start < now() - interval '5 minutes' AND query NOT LIKE '%pg_stat_activity%'"

# Index usage
psql -d journey_mining -c "
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY idx_blks_hit DESC"
```

### Alert Conditions

| Condition | Threshold | Action |
|-----------|-----------|--------|
| DB connection pool full | 100% | Restart Flask (kill connections) |
| Slow query | >1s | Check logs, optimize query |
| Disk full | >90% | Archive old data or add storage |
| Memory high | >80% | Restart Flask or add RAM |
| DB size | >50GB | Archive historical data |

---

## Maintenance Tasks

### Daily

- [x] Check logs for errors: `tail -100 /var/log/journey-mining.log | grep ERROR`
- [x] Verify health check passes: `curl -s http://localhost:5000/health`
- [x] Check disk usage: `df -h /` (should be <80%)

### Weekly

- [x] Run ANALYZE: `psql -d journey_mining -c "ANALYZE"`
- [x] Check slow queries: `psql -d journey_mining -c "SELECT query, calls, mean_time FROM pg_stat_statements LIMIT 10"`
- [x] Backup database: `pg_dump journey_mining > backup_$(date +%Y%m%d).sql`

### Monthly

- [x] Review performance: Compare clustering time vs baseline (should be <5s for 1000 events)
- [x] Vacuum table: `psql -d journey_mining -c "VACUUM ANALYZE"`
- [x] Check index usage: Run index usage query above
- [x] Update dependencies: `pip list --outdated`

### Quarterly

- [x] Full backup to offsite storage
- [x] Disaster recovery test (restore from backup)
- [x] Security audit (check for SQL injection, validate inputs)
- [x] Load test (simulate production workload)

---

## Emergency Procedures

### Data Loss / Corruption

**Immediate Actions:**
1. Stop Flask: `pkill -f gunicorn`
2. Stop PostgreSQL: `systemctl stop postgresql`
3. Do NOT restart or modify anything

**Recovery:**
```bash
# Restore from most recent backup
pg_restore -d journey_mining backup_20260415.sql

# Verify integrity
psql -d journey_mining -c "SELECT COUNT(*) FROM journey_events"
psql -d journey_mining -c "SELECT COUNT(*) FROM journey_sources"

# Restart services
systemctl start postgresql
systemctl start resume-optimizer
```

### Service Unavailable

**Quick restart:**
```bash
# Restart Flask
pkill -f gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app &

# Check health
sleep 2
curl http://localhost:5000/health
```

**Full restart:**
```bash
systemctl restart postgresql
systemctl restart resume-optimizer
sleep 5
curl http://localhost:5000/health
```

---

## Escalation Tree

| Issue | Level | Action | Contact |
|-------|-------|--------|---------|
| Slow query | L1 | Check logs, restart Flask | On-call engineer |
| DB unreachable | L1 | Restart PostgreSQL | On-call engineer |
| Data corruption | L2 | Restore from backup | DBA + Engineering |
| Complete outage | L2 | Full system restore | On-call + Manager |
| Ongoing issues | L3 | Post-mortem | Architecture team |

---

## Playbooks

### Playbook: Slow Clustering

1. ✓ Check logs: `tail -50 /var/log/journey-mining.log | grep clustering`
2. ✓ Run diagnostic: `psql -d journey_mining -c "ANALYZE"`
3. ✓ Check indexes: Run index usage query
4. ✓ If slow: Create missing indexes
5. ✓ Test: `python3 -c "from journey_clustering import cluster_events; cluster_events(1)"`
6. ✓ Monitor: Watch performance for 1 hour
7. ✓ Document: Note root cause and solution

### Playbook: High CPU Usage

1. ✓ Check process: `top -u $(whoami)`
2. ✓ Identify hot function: Use cProfile if needed
3. ✓ Check database queries: Are they slow?
4. ✓ Reduce worker count if Flask: `gunicorn -w 2 ...`
5. ✓ Or reduce batch size in clustering: Process 100 events at a time
6. ✓ Monitor recovery: Check that CPU drops after changes

---

## Runbook Template

For any outage:

1. **Time:** ________ (2026-04-15 10:30 UTC)
2. **Symptom:** What failed? ________
3. **Impact:** How many users? ________ affected
4. **Root Cause:** What was wrong? ________
5. **Resolution:** What did you do? ________
6. **Time to Fix:** ________ minutes
7. **Prevention:** How to avoid next time? ________

Post-mortem: Schedule 30-min review within 24 hours
