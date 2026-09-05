# IRI — Session Handoff, 2026-09-05

State at the end of a long session. Everything below is durable; nothing depends
on the session's context.

---

## 1. Where the work is

**S0 COMPLETE. S1 roughly half done. 289 IRI tests green, all pushed.**

| Stage | State |
|---|---|
| S0 — contract, 3 `ISecretStore` adapters, gateway, identity vault, entity redactor, tenant provisioning | ✅ |
| S1 — transcript segmentation | ✅ 142 turns, citations verified |
| S1 — Krisp OAuth + MCP transport + token store + routes, **live-verified** | ✅ |
| S1 — `IEvidenceSource` implementation | ⬜ **NEXT** |
| S1 — `FeedbackExtractor` | ⬜ the acceptance gate |
| S2–S7 | ⬜ |

Design: `DESIGN_..._2026-09-03.md` Rev 2.1 · Plan: `PLAN_..._2026-09-04.md` v1.6

---

## 2. ⚠ Live Krisp connection — DO NOT LOSE

Authorized 2026-09-05, **token valid until 2026-11-04**.

Credentials live in **`~/.config/resume-optimizer/krisp_oauth.env`** (mode 0600,
outside the repo, never committed). It holds `KRISP_CLIENT_ID`,
`KRISP_CLIENT_SECRET`, `KRISP_REDIRECT_URI` and **`FERNET_KEY`**.

**The `FERNET_KEY` is load-bearing.** The stored Krisp tokens are encrypted with
it. Start the backend with that file sourced or the tokens become
undecryptable and the browser authorization must be repeated:

```bash
cd backend
set -a; . ~/.config/resume-optimizer/krisp_oauth.env; set +a
DATABASE_URL="postgresql://gateway:gateway_secret@localhost:5433/ro_test" \
CLOUDLIFT_ENV=local ../.venv/bin/python app.py
```

Re-authorizing, if ever needed: `GET /api/iri/krisp/connect` with header
`user-id: 10`, open the returned `authorize_url`, approve. State is single-use.

---

## 3. Findings that only the live service produced

**MCP returns two representations.** Tool results carry `content` (markdown, for
humans) **and** `structuredContent` (parsed data). **The connector must use
`structuredContent`.** Parsing the markdown is fragile and lossy; an earlier
attempt read `content` and got nothing.

**Real response envelopes:**
```
search_meetings        -> structuredContent: {criteria, meetings:[{meeting_id,
                          name, date, duration_seconds, attendees, speakers}], count}
get_multiple_documents -> structuredContent: {results:[{id, document}],
                          requestedCount, foundCount}
```
`meeting_id` is 32-char lowercase hex. `foundCount` vs `requestedCount` detects
ids that did not resolve.

**⚠ LINE NUMBERS DRIFT — this changes the citation design.** The live transcript
is 50,424 chars; the archived copy is 50,593. The known-correct quote sits at
**line 488 live, line 495 archived** — same turn, same speaker, same timestamp.
Krisp re-processes transcripts.

**Consequence:** cite by `(meeting_id, turn index, timestamp)`, **never by line
number alone**. A line number is valid only against the exact byte stream it was
computed from. `RawEvidence` should carry the transcript it was segmented from so
a citation always resolves against the copy that produced it.

**Krisp issues CONFIDENTIAL clients.** Registration returns
`token_endpoint_auth_method=client_secret_basic` and a `client_secret` even when
`"none"` is requested. The exchange needs HTTP Basic client auth.

**Registration ignores requested scopes.** Asked for 3 read scopes; the client was
registered with 8, including `user::meetings:metadata::write` and
`user::recording::import`. The **granted token** carries only the 3 requested at
authorize time — the boundary held — but the client is *capable* of asking for
writes. Never widen the authorize request.

`speakers` in meeting metadata reported only one participant for a two-person
call. **Take speaker attribution from the transcript body, not the metadata.**

---

## 4. The defect worth remembering

The OAuth callback read the user from a `user-id` **request header**, but it is
reached by a **redirect from Krisp**, which carries no custom headers. Every test
passed because the tests sent the header — they exercised a path that cannot
occur. Identity now travels in the OAuth `state`.

This is the session's sharpest instance of a pattern that recurred perhaps ten
times across three sessions: **the half of an asymmetric operation you can verify
alone is the half that lies.** Publish succeeds with nobody listening. A
blank-guard passes on partial data. A boolean `redacted=true` passes on partial
redaction. A test client sends a header a browser never will.

---

## 5. CI

**Not green, and the remaining work is genuine test debt.**

Two infrastructure gaps fixed this session:
1. **No PostgreSQL service** — `init_db()` raises without a `postgresql://` URL
   since SQLite support was removed, so every DB test died at import. That was
   the cause of the mass `KeyError: 'token'`; the auth fixture could not register
   a user.
2. **NLTK corpora downloaded lazily** — surfaced as 59 `LookupError`s. Now
   fetched explicitly, like the spaCy model.

**Fixing #1 made the headline numbers WORSE** — 255→472 failures — because tests
that had been *erroring* now execute and fail on their own merits. The database
error was masking the debt. That is progress, not regression.

Also fixed: `test_pragma_foreign_keys_enabled` (ran a SQLite-only `PRAGMA` in a
Postgres-only app; rewritten to provoke a real FK violation) and
`test_legacy_user_id_fallback` (registered without activating, so login returned
403 with no `user_id`).

**No IRI test fails in CI.**

A full local run against a fresh database was in flight at session end; its
output is at `/tmp/.../scratchpad/full_run.txt` if it survived, otherwise re-run:
```bash
cd backend && DATABASE_URL=...ro_ci_full CLOUDLIFT_ENV=local PYTHONPATH=. \
  ../.venv/bin/python -m pytest tests/ -q --ignore=tests/test_live_smart_llm.py \
  --ignore=tests/test_bedrock_integration.py
```

**Standing instruction from the user:** turn CI green, pre-existing or not. **My
stated caveat:** where a test and the code disagree about intended behaviour,
surface the conflict rather than silently picking a side.

---

## 6. Environment

- **RTX 5090 clock capped at 1400 MHz** (`rtx5090-clock-cap-1400.service`) after
  a measured experiment: 1200 clean 25 min, **1400 clean 25 min**, uncapped
  **died in 100 s, twice**. Old `nvidia-clocklock` / `rtx5090-clock-lock` units
  are disabled and named in `Conflicts=`. ~60 delegations ran clean at 1400.
- FTAL harness: `force_swap_id` needs a swap **alias** (`qwen25-coder-32b`), not
  the HF id; task text needs a literal **repo-relative** `Target path:` line, and
  **the file must already exist** or intake refuses it.
- `cp` is aliased to interactive — use `cat >` redirection in scripts.
- The commit guard marks pre-commit passed on *invocation*, not success, and this
  repo has no `.pre-commit-config.yaml`.
- CloudLift: **11 of 12 contracts in three-way parity, 0 divergences**.
  `IFunctionExecution` is **blocked** (OpenWhisk ships a Docker client older than
  this host's daemon accepts), not pending.
- `IMessageQueue`: **3 receive defects across 2 adapters** (Artemis 2, SQS 1;
  Azure Service Bus none). S3/S4 must **prove receive, not publish**.

---

## 7. Immediate next step

Implement `IEvidenceSource` for Krisp in
`backend/iri/ingestion/krisp/source.py`, using `structuredContent`, mapping
`search_meetings` + `get_multiple_documents` onto `RawEvidence`, with
`fetch_since` paging by meeting date. Then `FeedbackExtractor`, which must
independently find the interviewer's feedback turn and cite it — the S1 gate.

---

## S1 acceptance gate — PASSED (2026-09-05)

`FeedbackExtractor` independently surfaced the known-correct answer from the
Employer A technical screen, with a verified citation.

```
OUTCOME: FINDINGS_PRODUCED
  turn 132 @ 01:04:16 [medium]
  claim: The candidate could have gone into more detail about how a RAG works.
  turn 132 @ 01:04:16 [medium]
  claim: The candidate might have considered a different approach regarding
         the model size and type.
```

The second finding is the actual rejection cause — the interviewer wanted an
off-the-shelf reasoning model rather than a self-hosted open-weight one.

**Deterministic narrowing before any model call:** 142 turns → 13 (a feedback
request detected at turn 129, plus the closing window). Prompt 2,632 chars.

### Design notes worth keeping

- **Citations are `(meeting_id, turn_index, timestamp)`, never line numbers.**
  Live and archived copies of the same meeting number lines differently, so a
  line citation drifts onto the wrong speaker while still looking plausible.
- **Every model citation is verified before it is accepted.** A finding whose
  quote does not appear in the turn it cites is *dropped*, compared with
  whitespace collapsed and case ignored and no weaker than that. This is the
  component's main safeguard: a fabricated finding looks specific, gets checked
  once, and is trusted thereafter.
- **`ANALYSIS_FAILED` and `INSUFFICIENT_EVIDENCE` are separate outcomes** and
  `AnalysisResult.__post_init__` refuses to construct an inconsistent one, in
  both directions. An earlier draft returned "no findings" when the model
  emitted garbage, which silently reported "nothing to see" for a malfunction.
- **Failure reasons carry the exception type name only** — never prompt,
  completion or transcript text, which is unredacted personal data and these
  reasons are logged and displayed. Pinned by a sentinel-word test.

### The golden transcript is NOT in the repo
`working-docs/` is gitignored and the repo is public. The real-transcript gate
must be run locally; committed tests use synthetic fixtures only.

---

## CI debt — root cause found (2026-09-05)

**The test suite is not hermetic.** A running suite holds live sockets to:

| Target | What |
|---|---|
| `127.0.0.1:8000` | FTAL gateway control plane |
| `[::1]:8529` | ArangoDB |
| `3.170.185.14:443` | CloudFront (`ord58`) — external internet |

Two consequences:

1. **It cannot be green in CI**, which has none of those services.
2. **It perturbs the infrastructure under it.** A full local run saturated the
   data plane's accept queue (2049 pending against a backlog of 2048) and a
   concurrent delegation failed with `Gateway error 503: Cannot connect to port
   8001`. The suite and the harness must not be run at the same time.

**Scale:** 3,637 tests collected. 29 test files reference network clients.
Markers already registered: `llm_required`, `real_pf`. `integration` is USED
(11 times) but NOT REGISTERED — it raises `PytestUnknownMarkWarning` and
deselects nothing.

**Proposed route to green** — needs a decision, since it changes what CI covers:
register `integration`, mark the live-service tests, and have CI run
`-m "not llm_required and not integration"`. Live tests stay runnable locally.
This is a scope change, not a bug fix: it makes CI honest about what it can
verify rather than pretending live-service tests pass.
