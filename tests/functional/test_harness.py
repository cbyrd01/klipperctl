"""Smoke tests for the tri-modality functional test harness itself.

These tests verify that the ``workflow_runner`` fixture cleanly skips when
``MOONRAKER_URL`` is unset, and (when set) that each modality's runner can
round-trip a trivial state read against the live printer. They intentionally
avoid any side-effect commands so they can run on any printer without
changing its state.
"""

from __future__ import annotations

import pytest


@pytest.mark.functional
@pytest.mark.asyncio
async def test_workflow_runner_reads_state(workflow_runner) -> None:  # type: ignore[no-untyped-def]
    """Each modality's runner must return a non-empty printer state string.

    This is the lightest possible end-to-end check — it proves connectivity,
    the preflight fixture, and all three runner implementations without
    touching temperatures or prints.
    """
    state = await workflow_runner.get_state()
    assert isinstance(state, str)
    assert state, f"{workflow_runner.modality} runner returned empty state"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_workflow_runner_reads_hotend_target(workflow_runner) -> None:  # type: ignore[no-untyped-def]
    """Each modality must be able to read the current extruder target."""
    target = await workflow_runner.get_hotend_target()
    assert isinstance(target, float)
    assert target >= 0.0
