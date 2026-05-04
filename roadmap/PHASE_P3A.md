# Phase P3-A: Security Remediation (Future Phase)

**Branch:** `feature/ro-phase-P3A-security`
**Model:** Opus (security audit) + Sonnet (implementation)
**Addresses:** Finding F7 (R7)
**Status:** PLANNED — Future session, lighter spec
**Estimated tests:** 25-30

---

## Objective

Remediate security vulnerabilities identified in the architecture analysis.
The resume optimizer has raw f-string SQL, bare user-id header auth, no input
validation, and wide-open CORS. This phase applies the same patterns from
gateway Phase 49 security remediation.

## Scope

### S1: SQL Injection Remediation
- Parameterize all f-string SQL (context_enrichment.py line 354 and similar)
- Audit all `conn.execute()` calls for string interpolation
- Replace with parameterized queries or ORM (if P2-F completed)

### S2: Authentication Upgrade
- Replace bare `user-id` header with JWT tokens
- Session management with configurable expiry
- Password hashing upgrade (werkzeug -> bcrypt, aligned with gateway)

### S3: Input Validation Middleware
- Request size limits (beyond 16MB file upload)
- Content type validation
- Rate limiting on LLM-heavy endpoints

### S4: CORS Restriction
- Restrict to known origins (localhost:3000 dev, production domain)
- Remove wildcard CORS

### S5: Dependency Audit
- Check requirements.txt for CVEs
- Update vulnerable packages
- Pin versions for reproducibility

## Acceptance Criteria

- [ ] Zero f-string SQL interpolation
- [ ] JWT auth with session management
- [ ] Input validation on all endpoints
- [ ] CORS restricted to known origins
- [ ] Zero high/critical CVEs in dependencies
- [ ] All existing tests pass with new auth

## User Gate P3-A

**Present:** Full security audit report with before/after vulnerability count,
JWT auth demo, input validation test results.
