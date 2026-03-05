````skill
---
name: add-feature
description: Standard end-to-end workflow for adding a new feature to ssd-testkit — from API/config changes through implementation, tests, and docs. Use when user says add feature, implement X, extend tool Y, 新增功能, 加 support, or requests any non-trivial code addition.
---

# Add Feature — ssd-testkit

Follow these steps **in order**. Do not skip steps.  
For adding a brand-new tool wrapper, use the `scaffold-testtool` skill instead.

---

## Step 1 — Understand the Scope

Before writing code, answer:

1. Which layer is affected?
   - `lib/testtool/<tool>/` — new capability in a tool wrapper
   - `framework/` — new test infrastructure
   - `tests/integration/` — new test scenario
   - `packaging/` — new build option

2. Does this touch the public API of a controller / config?  
   If yes, update `__init__.py` exports and `config.py` `DEFAULT_CONFIG`.

3. Does this need a new binary / external tool?  
   If yes, note it — binaries go in `tests/integration/<scenario>/bin/` and must be documented.

---

## Step 2 — Update Config (if applicable)

In `lib/testtool/<tool>/config.py`:

```python
DEFAULT_CONFIG = {
    # existing keys ...
    "new_param": "default_value",   # ADD here with a comment
}
```

Keep backward compatibility — new keys must have sensible defaults so existing callers don't break.

---

## Step 3 — Implement the Feature

### In a tool controller (`controller.py`)

- Add the new method to the controller class
- Use `self.config["new_param"]` to read config values
- Log entry and exit with `logger.info()`, internals with `logger.debug()`
- Raise typed exceptions from `exceptions.py` on failure

```python
def new_capability(self) -> SomeResult:
    logger.info(f"[{self.__class__.__name__}] Starting new_capability")
    try:
        result = self._do_work()
        logger.info(f"new_capability finished: {result}")
        return result
    except SomeSpecificError as e:
        raise MyToolError(f"new_capability failed: {e}") from e
```

### In `exceptions.py` (if new error conditions)

```python
class MyToolNewConditionError(MyToolError): ...
```

### In `__init__.py` (export new public symbols)

```python
from .controller import MyToolController
from .exceptions import MyToolError, MyToolNewConditionError  # add new ones
```

---

## Step 4 — Add Unit Tests

Location: `tests/unit/lib/<toolname>/test_<module>.py`

For every new method/function:
- Happy path (normal input → expected output)
- Error path (bad input / tool failure → expected exception)
- Edge case (empty input, timeout, etc.)

See the `write-unit-test` skill for full pytest conventions.

```powershell
# Run new unit tests to confirm they pass
pytest tests/unit/lib/<toolname>/ -v
```

---

## Step 5 — Update / Add Integration Test (if applicable)

Only if the feature needs end-to-end validation with real hardware:

- Add or update a test method in `tests/integration/<scenario>/test_*.py`
- Use `@pytest.mark.integration` and `@pytest.mark.hardware` (+ `@pytest.mark.admin` if needed)
- Add a corresponding fixture in `conftest.py` if new setup/teardown is required

```powershell
pytest tests/integration/<scenario>/test_<name>.py -v -s -m integration
```

---

## Step 6 — Update Docs

- If the feature changes user-facing behaviour, update the relevant `*_PLAN.md` (e.g., `PHM_PLAN.md`)
- If new config keys were added, add them to the Config JSON example in the test's `Config/` folder
- If new pytest markers are needed, add them to `pytest.ini`

---

## Step 7 — Verify Nothing is Broken

```powershell
# Full unit suite — must be green before committing
pytest tests/unit/ -v

# Quick smoke for the affected tool
python tests/verification/<toolname>/smoke_*.py
```

---

## Checklist Before Done

- [ ] `DEFAULT_CONFIG` updated with backward-compatible defaults
- [ ] New public symbols exported in `__init__.py`
- [ ] Typed exceptions raised, not bare `Exception`
- [ ] `logger.info/debug` calls (no `print()`)
- [ ] Unit tests added and passing
- [ ] Integration test updated (if applicable)
- [ ] Config JSON example updated (if applicable)
- [ ] `pytest tests/unit/ -v` is fully green
````
