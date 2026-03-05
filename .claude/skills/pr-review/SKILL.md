````skill
---
name: pr-review
description: Structured PR review checklist for ssd-testkit pull requests. Use when user asks to review a PR, check code changes, 審查 PR, review diff, or evaluate a branch before merge.
---

# PR Review — ssd-testkit

Apply this review in the order listed. Stop and flag any **BLOCKER** before proceeding.

---

## Review Order

### 1. Security (BLOCKER if failed)

- [ ] No credentials, tokens, API keys, or passwords hardcoded in source files
- [ ] No registry keys containing PII written without justification
- [ ] No `shell=True` in `subprocess` calls with user-controlled strings
- [ ] External binary paths come from config, not f-strings with user input
- [ ] No debug backdoors left open (`if True: skip_auth(...)`)

---

### 2. Architecture & Dependency Rules (BLOCKER if failed)

- [ ] Import direction respected: `tests → lib/testtool → lib/logger`; `framework` does NOT import from `lib/testtool`
- [ ] No cross-tool imports (`lib/testtool/burnin/` must NOT import from `lib/testtool/cdi/`)
- [ ] New symbols exported in `__init__.py`
- [ ] New config keys added to `DEFAULT_CONFIG` with safe defaults
- [ ] New exception types inherit from the tool's base exception class
- [ ] No legacy single-file wrappers (`lib/testtool/BurnIN.py` etc.) extended — use sub-packages

---

### 3. Correctness & Error Handling

- [ ] No bare `except:` — all caught exceptions are specific types
- [ ] Timeout scenarios handled (tool hangs → `TimeoutError` raised, not infinite block)
- [ ] Thread safety: shared state accessed under locks or `threading.Event`
- [ ] External process return codes checked; non-zero → raise typed exception
- [ ] File/path existence checked before use (`Path.exists()`)
- [ ] Config values validated (type, range) in `config.py`

---

### 4. Performance

- [ ] No blocking I/O on the main thread without timeout
- [ ] No polling loops tighter than 0.5 s sleep interval
- [ ] No unnecessary file reads in hot paths (cache if re-read in a loop)
- [ ] UI automation waits use `wait_for(state="visible")` / `wait_until_passes()`, not `time.sleep(N)` for long waits

---

### 5. Readability & Style

- [ ] Module, class, function names follow project conventions (`snake_case` / `PascalCase`)
- [ ] No `print()` in library code — only `logger.info/debug/warning/error`
- [ ] Docstrings on public classes and non-trivial functions
- [ ] Line length ≤ 120 characters
- [ ] No commented-out dead code committed (use git history instead)
- [ ] Constants named in `UPPER_SNAKE_CASE`; no magic numbers/strings inline

---

### 6. Test Coverage

- [ ] New public functions/methods have unit tests in `tests/unit/lib/<toolname>/`
- [ ] Happy path covered
- [ ] At least one error/exception path covered
- [ ] No tests that only pass when running as `real` hardware — unit tests must work with mocks
- [ ] Existing tests still pass (`pytest tests/unit/ -v` green)
- [ ] pytest markers applied correctly (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.)

---

### 7. Build & Packaging Impact

- [ ] If new files added to `lib/` → check if `packaging/build_config.yaml` needs updating
- [ ] If new binary required → documented in PR description; not committed to git
- [ ] `packaging/run_test.spec` updated if new hidden imports added for PyInstaller
- [ ] `requirements.txt` updated for any new third-party dependency

---

## Quick Sanity Commands

Run these before approving:

```powershell
# Unit tests green
pytest tests/unit/ -v

# No import errors in new modules
python -c "import lib.testtool.<toolname>"

# Check for obvious issues
python -m py_compile lib/testtool/<toolname>/*.py
```

---

## Review Summary Template

```
## PR Review Summary

**Security**: ✅ / ⚠️ <note>
**Architecture**: ✅ / ⚠️ <note>
**Correctness**: ✅ / ⚠️ <note>
**Performance**: ✅ / ⚠️ <note>
**Readability**: ✅ / ⚠️ <note>
**Test Coverage**: ✅ / ⚠️ <note>
**Packaging**: ✅ / N/A

**Verdict**: APPROVE / REQUEST CHANGES
**Blockers**: <list or "none">
**Suggestions**: <optional non-blocking improvements>
```
````
