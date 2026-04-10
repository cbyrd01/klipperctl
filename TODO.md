# klipperctl / moonraker-client Improvement TODO

Legend: `[ ]` NOT DONE · `[x]` DONE · `commit: <sha>` · `pushed: yes/no`

A phase is DONE only when every task is `[x]` **and** every phase exit criterion is `[x]`.
Every phase exit criteria list includes: all unit tests passing, no regressions, ruff/mypy clean, committed AND pushed.

Plan reference: `/Users/chris/.claude/plans/replicated-wandering-aurora.md`

---

## Phase 0 — Packaging Fix (CRITICAL, local-only)

**Goal:** sibling-checkout + local-wheel workflow is correct, explicit, and documented. **No PyPI upload.**

**Phase Exit Criteria:**
- [x] `pytest tests/unit` green in both klipperctl (247 passed, 1 skipped) and moonraker-client (122 passed)
- [x] `python -m build` clean in both repos
- [x] Local wheels install in a throwaway venv and `klipperctl --help` works (including `klipperctl[tui]`)
- [x] ruff + mypy clean in both repos
- [x] No regressions in existing functional suites (skipped without MOONRAKER_URL)
- [ ] Committed AND pushed to origin
- [x] **Nothing uploaded to PyPI**

### Tasks
- [x] Fix misleading `moonraker-client>=0.1.0` dep in klipperctl/pyproject.toml (use plain name marker; document two-step install)
  - Acceptance: dep line matches reality; throwaway-venv install succeeds
  - commit: (pending)   pushed: —
- [x] Verify local build for moonraker-client
  - Acceptance: `python -m build` produces sdist + wheel with correct metadata
  - commit: (pending)   pushed: —
- [x] Verify local build for klipperctl
  - Acceptance: `python -m build` produces sdist + wheel
  - commit: (pending)   pushed: —
- [x] Throwaway-venv smoke test from local wheels
  - Acceptance: `pip install dist/moonraker_client-*.whl dist/klipperctl-*.whl` then `klipperctl --help` works
  - commit: (pending)   pushed: —
- [x] Update README install section (remove false `pip install klipperctl` claim, document two-step git install + sibling-checkout dev path)
  - Acceptance: README matches actual working install steps
  - commit: (pending)   pushed: —
- [x] Fix pre-existing ruff format drift in `moonraker-client/src/moonraker_client/helpers.py` (unblocks exit criteria)
  - Acceptance: `ruff format --check` clean in moonraker-client
  - commit: (pending)   pushed: —

---

## Phase 1 — Reliability & Error Handling (HIGH)

**Goal:** remove silent failure paths, bound worst-case waits, surface real errors.

**Phase Exit Criteria:**
- [ ] All existing unit tests pass in both repos
- [ ] New unit tests added for each fix and passing
- [ ] ruff + mypy clean
- [ ] No regressions
- [ ] Committed AND pushed

### Tasks
- [ ] Surface TUI poll-worker errors via `self.notify` with throttling (app.py:79-109)
  - Acceptance: `tests/unit/test_tui_app.py::test_poll_error_notifies` passes; repeat errors don't spam
  - commit: —   pushed: —
- [ ] Add timeout wrapper to TUI cli_command worker (app.py:199-200)
  - Acceptance: `test_tui_app.py::test_cli_command_timeout` passes; stuck command returns exit 124
  - commit: —   pushed: —
- [ ] Add `poll_interval` constructor arg + exponential backoff on consecutive errors
  - Acceptance: `test_tui_app.py::test_poll_backoff_on_errors` passes
  - commit: —   pushed: —
- [ ] Decouple FileNotFoundError mapping in cli.py:103-105 (catch at real call sites)
  - Acceptance: `test_cli.py::test_file_not_found_is_not_user_input` passes
  - commit: —   pushed: —
- [ ] Narrow bare `except Exception` in `_logs_tail` (server.py:161-166) with consecutive-failure warning
  - Acceptance: new test verifies `KeyboardInterrupt` propagates; transient `MoonrakerError` keeps loop alive
  - commit: —   pushed: —
- [ ] Narrow bare `except Exception` in `temps --watch` loop (printer.py:171)
  - Acceptance: new test verifies `KeyboardInterrupt` propagates
  - commit: —   pushed: —

---

## Phase 2 — Test Harness Overhaul

**Goal:** reusable fixtures — (a) skip cleanly when no printer, (b) guarantee ready state via firmware-restart recovery, (c) run same workflow across library / CLI / TUI modalities.

**Phase Exit Criteria:**
- [ ] Unit tests still green (harness does not affect them)
- [ ] With `MOONRAKER_URL` unset: all functional tests skip cleanly with clear message
- [ ] With `MOONRAKER_URL` set + unreachable printer: skip cleanly
- [ ] With `MOONRAKER_URL` set + not-ready printer: firmware-restart recovery triggers; proceeds if ready, skips otherwise
- [ ] Existing single-step functional tests still pass untouched
- [ ] ruff + mypy clean
- [ ] Committed AND pushed

### Tasks
- [ ] Extend `tests/functional/conftest.py` with `moonraker_url`, `live_client`, `printer_ready`, `fresh_client` fixtures
  - Acceptance: fixtures used by at least one smoke test; skip paths verified
  - commit: —   pushed: —
- [ ] Create `tests/functional/_harness.py` with `LibraryRunner`, `CliModalityRunner`, `TuiRunner` implementing shared interface
  - Acceptance: all three runners implement: `set_hotend_temp`, `wait_until_temp`, `upload_sentinel_gcode`, `start_print`, `cancel_print`, `get_state`, `send_gcode`, `tail_logs_for`
  - commit: —   pushed: —
- [ ] Add `modality` + `workflow_runner` parametrized fixtures
  - Acceptance: a one-line smoke test parametrizes across library/cli/tui cleanly
  - commit: —   pushed: —
- [ ] Add firmware-restart recovery to `printer_ready` fixture
  - Acceptance: forcing klippy to shutdown state triggers `restart_firmware` and waits for ready (env-overridable timeout)
  - commit: —   pushed: —

---

## Phase 3 — Multi-Step Functional Workflows

**Goal:** real end-to-end flows across all three modalities.

**Phase Exit Criteria:**
- [ ] `MOONRAKER_URL=... pytest tests/functional/test_workflows.py --functional` green for all 3 modalities
- [ ] Each workflow bounded in wallclock and cleans up its state in teardown
- [ ] No regressions in other functional tests
- [ ] Committed AND pushed

### Tasks
- [ ] heat-and-verify workflow (set temp → wait reached → verify state → cool down)
  - Acceptance: passes against live printer for library, cli, tui
  - commit: —   pushed: —
- [ ] start-and-cancel workflow (upload sentinel → start → verify printing → cancel → verify standby)
  - Acceptance: passes against live printer for library, cli, tui
  - commit: —   pushed: —
- [ ] gcode-log roundtrip workflow (send M118 marker → tail logs → assert seen)
  - Acceptance: passes against live printer for library, cli, tui
  - commit: —   pushed: —

---

## Phase 4 — Transport & UX Polish (MEDIUM)

**Phase Exit Criteria:**
- [ ] Unit + functional tests green
- [ ] New transport unit tests cover timeout propagation, 4xx fail-fast, version mismatch warning, progress callback
- [ ] ruff + mypy clean
- [ ] No regressions
- [ ] Committed AND pushed

### Tasks
- [ ] Propagate constructor timeout through WebSocket (replace `_transport.py:261` hardcoded 30s)
  - Acceptance: new unit test asserts custom timeout honored
  - commit: —   pushed: —
- [ ] Classify retryable vs permanent errors in reconnect loop (`_transport.py:307-318`); expose `connection_lost` signal
  - Acceptance: 4xx / auth failure stops retrying; new test verifies
  - commit: —   pushed: —
- [ ] Optional notification-error hook (`_transport.py:301-302`)
  - Acceptance: owner can register handler-error callback; test verifies invocation
  - commit: —   pushed: —
- [ ] Moonraker version check on connect with `MIN_SUPPORTED_MOONRAKER_VERSION`
  - Acceptance: test asserts warning logged on mismatch
  - commit: —   pushed: —
- [ ] Local retry decorator on helpers (`server_info`, `printer_info`, `files_upload`)
  - Acceptance: test verifies up to 3 retries on transient network errors
  - commit: —   pushed: —
- [ ] Progress callback on `files_upload`/download + `rich.progress.Progress` bar in `klipperctl files upload/download`
  - Acceptance: test verifies callback fires; manual smoke shows progress bar
  - commit: —   pushed: —

---

## Phase 5 — Docs, Typing, Footer, LOW items

**Phase Exit Criteria:**
- [ ] Unit + functional tests green
- [ ] ruff + mypy clean
- [ ] No regressions
- [ ] Committed AND pushed

### Tasks
- [ ] Tighten callback type hints on `_transport.on()`/`off()`
  - Acceptance: `NotificationHandler` alias exported and used
  - commit: —   pushed: —
- [ ] Add `Footer()` to each TUI screen `compose()` so BINDINGS render
  - Acceptance: TUI tests assert footer present; manual smoke shows shortcuts
  - commit: —   pushed: —
- [ ] README multi-printer TOML profile example + Troubleshooting section
  - Acceptance: sections exist, examples copy-pasteable
  - commit: —   pushed: —
- [ ] Docstrings on private helpers in both repos (spot-fix the gaps found in review)
  - Acceptance: ruff lint clean; ruff `D`-rules optional
  - commit: —   pushed: —
