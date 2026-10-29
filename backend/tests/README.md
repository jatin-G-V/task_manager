# Sorted validation suite

Layers, bottom to top: gate, pure logic, API + DB, agent, app (manual), failure/latency.
Assert on database state and API responses, never on the chat wording.

## One-time setup (backend/ folder)
1. A second, free Supabase project (for example `sorted-test`) with the same tables and RLS
   (`test_project_schema.sql`).
2. `.env.test` copied from `.env.test.example`: every variable of your `.env`, but with the TEST
   project's URL and keys, and `SORTED_TEST_ENV=1`. Keep it out of git.
3. `pip install -r requirements-dev.txt`

## Run
    pytest -m gate        # backend starts, auth basics              (needs test project)
    pytest -m security    # user isolation + RLS, zero tolerance     (needs test project)
    pytest -m logic       # recommendation, clash, time text, past-time rules, dedupe shortlist (no network)
    pytest tests/api/test_p3_actions.py   # complete / update / delete / recurring / cross-user routes
    pytest                # everything except agent tests
    pytest -m agent -s    # real LLM calls (duplicate judge accuracy), slow, uses quota

## What each file covers
    api/test_p0_gate.py            health, routes registered, 401 without or with a bad token
    api/test_p1_security.py        A cannot read, change or delete B's rows (API and RLS)
    api/test_p3_actions.py         complete (status, completed_at, History), recurring next occurrence,
                                   injected DB error, update rules, delete, cross-user update/complete/delete
    unit/test_recommendation.py    pinned window, at-risk, ordering, blocked, energy mode, dashboard counts,
                                   determinism
    unit/test_clash.py             overlap rules for exact-time tasks
    unit/test_taskfmt.py           "tomorrow at 10:00 AM", windows, deadlines
    unit/test_task_validation.py   past-time, window, recurrence-field, duration and consistency rules
    unit/test_dedupe_shortlist.py  which open tasks the duplicate judge gets to see
    agent/test_dedupe_judge.py     30 labelled pairs against the real judge (needs GROQ key)

## Tests named FINDING
They probe behaviour that looks wrong in the current code. A failure is a real bug to fix.

## Tracker (one row per case; keep it in a sheet)
| ID | Area | Case | Input | Expected (DB state) | Actual | Pass/Fail | Evidence |
|----|------|------|-------|---------------------|--------|-----------|----------|
