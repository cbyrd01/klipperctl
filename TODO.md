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
- [x] Committed AND pushed to origin (klipperctl 7470543, moonraker-client cd4d4c0)
- [x] **Nothing uploaded to PyPI**

### Tasks
- [x] Fix misleading `moonraker-client>=0.1.0` dep in klipperctl/pyproject.toml (use plain name marker; document two-step install)
  - Acceptance: dep line matches reality; throwaway-venv install succeeds
  - commit: 7470543   pushed: yes
- [x] Verify local build for moonraker-client
  - Acceptance: `python -m build` produces sdist + wheel with correct metadata
  - commit: 7470543   pushed: yes
- [x] Verify local build for klipperctl
  - Acceptance: `python -m build` produces sdist + wheel
  - commit: 7470543   pushed: yes
- [x] Throwaway-venv smoke test from local wheels
  - Acceptance: `pip install dist/moonraker_client-*.whl dist/klipperctl-*.whl` then `klipperctl --help` works
  - commit: 7470543   pushed: yes
- [x] Update README install section (remove false `pip install klipperctl` claim, document two-step git install + sibling-checkout dev path)
  - Acceptance: README matches actual working install steps
  - commit: 7470543   pushed: yes
- [x] Fix pre-existing ruff format drift in `moonraker-client/src/moonraker_client/helpers.py` (unblocks exit criteria)
  - Acceptance: `ruff format --check` clean in moonraker-client
  - commit: moonraker-client cd4d4c0   pushed: yes

---

## Phase 1 — Reliability & Error Handling (HIGH)

**Goal:** remove silent failure paths, bound worst-case waits, surface real errors.

**Phase Exit Criteria:**
- [x] All existing unit tests pass in both repos (252 klipperctl, 122 moonraker-client)
- [x] New unit tests added for each fix and passing
- [x] ruff + mypy clean
- [x] No regressions
- [x] Committed AND pushed (1d05145)

### Tasks
- [x] Surface TUI poll-worker errors via `self.notify` with throttling (app.py)
  - Acceptance: `test_tui_app.py::test_poll_error_notifies_and_backs_off` passes; repeat identical errors don't re-notify
  - commit: 1d05145   pushed: yes
- [x] Add timeout wrapper to TUI cli_command worker
  - Acceptance: `test_tui_app.py::test_cli_command_timeout_returns_exit_124` passes
  - commit: 1d05145   pushed: yes
- [x] Add `poll_interval` constructor arg + exponential backoff on consecutive errors
  - Acceptance: `test_tui_app.py::test_poll_success_after_error_resets_backoff` passes
  - commit: 1d05145   pushed: yes
- [x] Decouple FileNotFoundError mapping in cli.py (catch at real call site in print_cmd.start)
  - Acceptance: `test_stray_file_not_found_is_not_user_input` + `test_remote_file_not_found_exits_3` pass
  - commit: 1d05145   pushed: yes
- [x] Narrow bare `except Exception` in `_logs_tail` (server.py) with consecutive-failure warning
  - Acceptance: now catches only `MoonrakerError`, so `KeyboardInterrupt` propagates; warns after 5 consecutive failures
  - commit: 1d05145   pushed: yes
- [x] Narrow bare `except Exception` in `_show_temps` (printer.py)
  - Acceptance: narrowed to `MoonrakerError` with debug log
  - commit: 1d05145   pushed: yes

---

## Phase 2 — Test Harness Overhaul

**Goal:** reusable fixtures — (a) skip cleanly when no printer, (b) guarantee ready state via firmware-restart recovery, (c) run same workflow across library / CLI / TUI modalities.

**Phase Exit Criteria:**
- [x] Unit tests still green (252 passed, 1 skipped)
- [x] With `MOONRAKER_URL` unset: all new functional tests skip cleanly with clear message (verified via `pytest tests/functional/test_harness.py --functional`, 6 skipped)
- [x] With `MOONRAKER_URL` set + unreachable printer: live_client fixture skips (verified by inspection of conftest.py skip paths)
- [x] With `MOONRAKER_URL` set + not-ready printer: firmware-restart recovery triggers; proceeds if ready, skips otherwise (via `printer_ready` fixture)
- [x] Existing single-step functional tests still pass untouched (no changes to `test_printer.py`, `test_all_commands.py`, `test_tui.py`)
- [x] ruff + mypy clean
- [x] Committed AND pushed (6a8299d)

### Tasks
- [x] Extend `tests/functional/conftest.py` with `moonraker_url`, `live_client`, `printer_ready`, `fresh_client` fixtures
  - Acceptance: new `tests/functional/test_harness.py` smoke test exercises all three runner modalities via the fixtures; skip path verified
  - commit: 6a8299d   pushed: yes
- [x] Create `tests/functional/_harness.py` with `LibraryRunner`, `CliModalityRunner`, `TuiRunner` implementing shared interface
  - Acceptance: all three runners implement `get_state`, `set_hotend_temp`, `set_bed_temp`, `get_hotend_target`, `wait_until_temp`, `upload_sentinel_gcode`, `start_print`, `cancel_print`, `send_gcode`, `tail_logs_for` (async); enforced by abstract `WorkflowRunner` base class
  - commit: 6a8299d   pushed: yes
- [x] Add `modality` + `workflow_runner` parametrized fixtures
  - Acceptance: `test_harness.py::test_workflow_runner_reads_state[library|cli|tui]` parametrizes cleanly (6 tests collected, 6 skipped without MOONRAKER_URL)
  - commit: 6a8299d   pushed: yes
- [x] Add firmware-restart recovery to `printer_ready` fixture
  - Acceptance: fixture calls `restart_firmware` with env-overridable `KLIPPERCTL_TEST_READY_TIMEOUT` (default 60s); skips (does not fail) if printer cannot reach ready state
  - commit: 6a8299d   pushed: yes

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
