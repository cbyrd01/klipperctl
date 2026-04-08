"""Shared test fixtures for klipperctl."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--functional",
        action="store_true",
        default=False,
        help="Run functional tests against a live Moonraker server",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--functional"):
        skip = pytest.mark.skip(reason="Need --functional flag to run")
        for item in items:
            if "functional" in item.keywords:
                item.add_marker(skip)
