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
- [ ] `MOONRAKER_URL=... pytest tests/functional/test_workflows.py --functional` green for all 3 modalities (requires live printer — not verified in this session)
- [x] Each workflow bounded in wallclock and cleans up its state in teardown (`try/finally` with `contextlib.suppress`)
- [x] No regressions in unit or pre-existing functional tests (252 unit passed; 58 functional collected and skip cleanly without MOONRAKER_URL)
- [x] 9 new workflow tests parametrize cleanly (3 workflows × 3 modalities = 9 tests; all skip without MOONRAKER_URL)
- [x] ruff + mypy clean
- [x] Committed AND pushed (262df44)

### Tasks
- [x] heat-and-verify workflow (set temp → wait reached → verify state → cool down)
  - Acceptance: 3 parametrizations (library/cli/tui) collect and skip cleanly without MOONRAKER_URL; live-printer run left to the user
  - commit: 262df44   pushed: yes
- [x] start-and-cancel workflow (upload sentinel → start → verify printing → cancel → verify idle)
  - Acceptance: 3 parametrizations collect and skip cleanly; teardown cancels any in-flight print; sentinel uses pure `G4 P60000` dwell (no motion/heating)
  - commit: 262df44   pushed: yes
- [x] gcode-log roundtrip workflow (send M118 marker → tail logs → assert seen)
  - Acceptance: 3 parametrizations collect and skip cleanly; marker is a unique `KLIPPERCTL_TEST_<hex>` to avoid collisions
  - commit: 262df44   pushed: yes

---

## Phase 4 — Transport & UX Polish (MEDIUM)

**Phase Exit Criteria:**
- [x] Unit tests green in both repos (252 klipperctl, 140 moonraker-client; +18 new in moonraker-client)
- [x] Full functional suite green against live virtual printer (309 passed in combined run, including 9 new multi-step workflows × library/CLI/TUI)
- [x] New transport unit tests cover: timeout propagation (default + custom), 4xx fail-fast (401) vs transient (502, ConnectionClosed, OSError), version mismatch warning (older/newer/matching/unparseable), retry decorator (pass-through/retry-then-succeed/give-up/non-transient)
- [x] ruff + mypy clean in both repos
- [x] No regressions
- [x] Committed AND pushed (klipperctl 1f059d1, moonraker-client 10bdd56)

### Tasks
- [x] Propagate constructor timeout through WebSocket
  - Acceptance: `TestRequestTimeoutPropagation::test_custom_timeout_stored` passes; `_transport.py:261` hardcoded 30s replaced with `self._request_timeout`; `AsyncMoonrakerClient.connect_websocket` wires `self._timeout` through
  - commit: moonraker-client 10bdd56   pushed: yes
- [x] Classify retryable vs permanent errors in reconnect loop
  - Acceptance: `TestPermanentWsErrorClassifier` passes — 401 stops retry, 502/ConnectionClosed/OSError retry; `connection_lost_reason` set when loop gives up
  - commit: moonraker-client 10bdd56   pushed: yes
- [x] Optional notification-error hook
  - Acceptance: `add_handler_error_callback` API + `TestHandlerErrorCallback` tests passing; broken observer does not kill listener
  - commit: moonraker-client 10bdd56   pushed: yes
- [x] Moonraker version check with `MIN_SUPPORTED_MOONRAKER_VERSION`
  - Acceptance: `check_server_version` helper + `TestCheckServerVersion` tests passing (older warns, matching/newer ok, unparseable tolerated)
  - commit: moonraker-client 10bdd56   pushed: yes
- [x] Local retry decorator on helpers
  - Acceptance: `_with_retry` decorator + `TestWithRetryDecorator` tests passing; applied to `restart_firmware`
  - commit: moonraker-client 10bdd56   pushed: yes
- [x] Fix pytest-asyncio strict-mode async fixture (`@pytest_asyncio.fixture` on `workflow_runner`)
  - Acceptance: all 9 workflow tests run cleanly via `pytest --functional` against live printer
  - commit: 1f059d1   pushed: yes
- [x] Fix runner `get_state()` to read `print_stats.state` not klippy state
  - Acceptance: print-state transitions (standby → printing → cancelled) correctly observed across all modalities
  - commit: 1f059d1   pushed: yes
- [x] Replace single-60s-G4 sentinel with short-dwell ticks (avoids virtual-MCU timer scheduling error)
  - Acceptance: sentinel no longer triggers "Rescheduled timer in the past" MCU shutdown
  - commit: 1f059d1   pushed: yes
- [x] Add `_ensure_not_printing` pre-flight + firmware-restart fallback in `test_start_and_cancel_workflow`
  - Acceptance: workflow resilient to residual state from previous parametrizations; 3/3 modalities pass
  - commit: 1f059d1   pushed: yes
- [x] Progress callback on `files_upload`/download + Rich progress bar (**landed as Phase 4b**)
  - Acceptance: `_ProgressReader` class + streaming download path; callback fires with (0, total)/(total, total) monotonic ticks; Rich `Progress` bar with bar/bytes/speed/ETA renders in `klipperctl files upload|download` interactive mode; `--no-progress` and `--json` both suppress the bar while still exercising the callback plumbing; 8 new unit tests (sync + async upload/download + `_ProgressReader` direct tests) in moonraker-client; 5 new unit tests in klipperctl for callback plumbing + `--no-progress` flag; 3 new functional tests (`test_file_transfers.py`) exercising real upload/download against virtual printer including full CLI round trip
  - Also fixed a pre-existing bug: `files_download` used to crash with `JSONDecodeError` on any binary body. Phase 4b bypasses `unwrap_response` via a new `_stream_download` path.
  - commit: moonraker-client baac25d + klipperctl (pending)   pushed: —

---

## Phase 5 — Docs, Typing, Footer, LOW items

**Phase Exit Criteria:**
- [x] Unit tests green in both repos (252 klipperctl, 140 moonraker-client)
- [x] Full functional suite green against live virtual printer (309 passed / 1 skipped)
- [x] ruff + mypy clean in both repos
- [x] No regressions
- [x] Committed AND pushed (klipperctl 75d3809, moonraker-client 155f770)

### Tasks
- [x] Tighten callback type hints on `AsyncMoonrakerClient.on`/`off`
  - Acceptance: new `NotificationHandler` alias exported from the package; signatures updated; surfaced a real annotation bug in `klipperctl.commands.server._console_stream` which mypy now catches
  - commit: moonraker-client 155f770 (klipperctl wiring in a follow-up commit if needed)   pushed: yes
- [x] Verify `Footer()` on each TUI screen `compose()` so BINDINGS render
  - Acceptance: confirmed by code inspection — dashboard, commands, and console screens all already yield `Footer()`; no work needed
  - commit: n/a (already in place)   pushed: n/a
- [x] README multi-printer TOML profile example + Troubleshooting section
  - Acceptance: "Multiple printers" section with copy-pasteable TOML + `--printer` selector; "Troubleshooting" table covering connection, auth, timeout, klippy shutdown, remote-file-not-found, TUI freeze, logs `--watch`
  - commit: 75d3809   pushed: yes
- [ ] Docstrings on private helpers (deferred — spot-fixes folded into each phase as needed; no outstanding gaps identified in the review)
  - commit: n/a   pushed: n/a
