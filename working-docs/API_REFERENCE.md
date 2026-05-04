# Journey Mining API Reference

**Base URL:** `http://localhost:5000/api` | **Auth:** User-ID header | **Format:** JSON

---

## Overview

Journey Mining API provides endpoints for watermark tracking, event scoring, deduplication, and clustering. All phases of the pipeline are exposed.

---

## Common Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "data": { /* phase-specific data */ },
  "metadata": {
    "execution_time_ms": 42,
    "user_id": 1,
    "timestamp": "2026-04-15T10:30:00Z"
  }
}
```

### Error Response (4xx/5xx)

```json
{
  "success": false,
  "error": "Description of what went wrong",
  "error_code": "VALIDATION_ERROR"
}
```

---

## Phase 1: Watermarks

### Get Latest Watermarks

**GET `/journey/watermarks`** — Retrieve previous mining watermarks for incremental mining

**Auth:** `user-id` header required

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "files": "2026-04-14T10:30:00Z",
    "git": "2026-04-14T10:30:00Z"
  }
}
```

---

## Phase 3: Scoring

### Score Single Event

**POST `/journey/score`** — Assign significance score (1-5) to event

**Auth:** `user-id` header required

**Request Body:**
```json
{
  "source_id": 123,
  "title": "feat: Add authentication",
  "full_text": "Added JWT with rate limiting. Technology: Flask, PyJWT",
  "source_type": "git_commit"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "source_id": 123,
    "significance_score": 3,
    "classification": "FEAT",
    "score_breakdown": {
      "baseline": 1,
      "feat_bonus": 2
    }
  }
}
```

**Scoring Rules:**
- Baseline: 1 (all sources)
- Feat commit: +2
- Governance keywords: +2
- Completion: +1
- Impact: +1
- Tech breadth (5+): +1
- **Max: 5**

---

## Phase 4a: Deduplication

### Deduplicate Sources

**POST `/journey/deduplicate`** — Find and merge duplicate sources

**Auth:** `user-id` header required

**Request Body:**
```json
{
  "fuzzy_threshold": 0.8,
  "exact_only": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "exact_duplicates": 2,
    "fuzzy_duplicates": 1,
    "merged_count": 3,
    "removed_ids": [15, 42, 99],
    "merged_references": {
      "12": [15],
      "40": [42]
    }
  }
}
```

---

## Phase 4b: Clustering

### Cluster Events

**POST `/journey/cluster`** — Group events within time windows

**Auth:** `user-id` header required

**Request Body:**
```json
{
  "window_days": 7,
  "similarity_threshold": 0.7
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "total_events": 45,
    "clusters_created": 8,
    "cluster_head_count": 8,
    "average_cluster_size": 5.6
  }
}
```

### Get Cluster Summary

**GET `/journey/cluster-summary`** — Summary statistics on clustering

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "total_events": 45,
    "cluster_count": 8,
    "average_cluster_size": 5.625,
    "largest_cluster_size": 12
  }
}
```

---

## Full Pipeline

### Run Full Pipeline

**POST `/journey/pipeline`** — Execute all phases (watermark → score → dedup → cluster)

**Request Body:**
```json
{
  "watermark_aware": true,
  "deduplicate": true,
  "cluster": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "watermarks": { /* Phase 1 */ },
    "deduplication": { /* Phase 4a */ },
    "clustering": { /* Phase 4b */ }
  },
  "metadata": {
    "execution_time_ms": 450
  }
}
```

---

## Code Examples

**Python:**
```python
import requests
BASE_URL = "http://localhost:5000/api"
headers = {"user-id": "1"}

# Score event
resp = requests.post(f"{BASE_URL}/journey/score",
  json={"source_id": 123, "title": "feat: Auth", "source_type": "git_commit"},
  headers=headers)
print(resp.json()["data"]["significance_score"])  # 3

# Cluster
resp = requests.post(f"{BASE_URL}/journey/cluster",
  json={"window_days": 7},
  headers=headers)
print(resp.json()["data"]["clusters_created"])  # 8
```

**cURL:**
```bash
curl -X POST http://localhost:5000/api/journey/score \
  -H "user-id: 1" \
  -H "Content-Type: application/json" \
  -d '{"source_id": 123, "title": "feat: Auth", "source_type": "git_commit"}'
```

---

## Error Responses

### 400 Bad Request
```json
{
  "success": false,
  "error": "Missing required field: source_type",
  "error_code": "VALIDATION_ERROR"
}
```

### 401 Unauthorized
```json
{
  "success": false,
  "error": "Missing user-id header",
  "error_code": "AUTH_REQUIRED"
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "error": "Database connection failed",
  "error_code": "DATABASE_ERROR"
}
```

---

## Full Docs

- **Deployment:** `DEPLOYMENT_GUIDE.md`
- **Operations:** `OPERATIONS_RUNBOOK.md`
- **Migration:** `MIGRATION_GUIDE.md`
