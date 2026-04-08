# Code Quality Review Progress

## Phase 1: Critical Bug Fixes
- [x] 1a. moonraker-client: Fix `machine_update_rollback()` missing `name` param
- [x] 1b. klipperctl: Pass `name` to rollback API call
- [x] 1c. moonraker-client: Defensive async file upload
- [x] 1-tests. Run tests in both repos and commit

## Phase 2: Security Hardening
- [x] 2a. Config file permissions (chmod 0o600)
- [x] 2b. Path traversal validation on file operations
- [x] 2c. Add confirmation to `power on` / `power off`
- [x] 2d. Safer JSON serialization
- [x] 2-tests. Run tests in both repos and commit

## Phase 3: Error Handling Improvements
- [x] 3a. moonraker-client: Narrow exception catches in helpers.py
- [x] 3b. moonraker-client: Export `JsonRpcError` from public API
- [x] 3c. klipperctl: Narrow exception catches across all command modules
- [x] 3d. klipperctl: Improve peripheral enumeration error visibility
- [x] 3e. klipperctl: Add error-path tests
- [x] 3-tests. Run tests, ruff, mypy and commit

## Phase 4: Type Safety
- [x] 4a. Fix `client: object` parameter types
- [x] 4b. Type `human_fn` properly in output.py
- [x] 4c. Type `_write_toml` file parameter
- [x] 4d. Tighten mypy configuration
- [x] 4-tests. Run mypy and tests, commit

## Phase 5: Code Organization & DRY
- [x] 5a. Extract response unwrapping helper
- [x] 5b. Extract watch/poll loop
- [x] 5c. Move inline imports to module level
- [x] 5d. moonraker-client: Add async helper functions
- [x] 5-tests. Run full test suites, commit

## Phase 6: Tooling, Tests & Documentation
- [ ] 6a. Enable additional Ruff rules
- [ ] 6b. Fill test coverage gaps (klipperctl)
- [ ] 6c. Fill test coverage gaps (moonraker-client)
- [ ] 6d. Update documentation (CLAUDE.md, README.md, docs/CLI.md)
- [ ] 6e. Final test run (unit + functional if available)
- [ ] 6f. Final commit and remove this TODO.md
