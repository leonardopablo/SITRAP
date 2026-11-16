"""Opt-in browser test against an isolated real PostgreSQL test database."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.test_cuyes import farm  # noqa: F401 -- shared fixture, no production seed


@pytest.mark.skipif(os.environ.get("SITRAP_BROWSER_TESTS") != "1", reason="Set SITRAP_BROWSER_TESTS=1 for the real Django/browser test.")
@pytest.mark.django_db(transaction=True)
def test_cuyes_real_browser(live_server, farm):  # noqa: F811 -- imported pytest fixture
    for actor in [farm["worker"], farm["admin"]]:
        actor.set_password("Cuyes-local-test-123!")
        actor.save()
    env = {
        **os.environ, "SITRAP_TEST_API": live_server.url,
        "SITRAP_TEST_PEN": str(farm["p1"].id), "SITRAP_TEST_SHED": str(farm["g1"].id),
        "SITRAP_TEST_MALES": str(farm["pm"].id), "SITRAP_TEST_FEMALES": str(farm["pf"].id),
    }
    executable = "npm.cmd" if os.name == "nt" else "npm"
    result = subprocess.run(
        [executable, "exec", "playwright", "test", "--", "--config", "playwright.cuyes.config.ts"],
        cwd=Path(__file__).resolve().parent.parent / "frontend",
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
