import os
import subprocess
from pathlib import Path

import pytest

from tests.test_cuyes import farm  # noqa: F401
from tests.test_cuyes_sales import market  # noqa: F401


@pytest.mark.skipif(os.environ.get("SITRAP_BROWSER_TESTS") != "1", reason="Set SITRAP_BROWSER_TESTS=1 for real sales browser tests.")
@pytest.mark.django_db(transaction=True)
def test_sales_real_browser(live_server, market):  # noqa: F811 -- imported pytest fixture
    for actor in [market["admin"], market["worker"], market["driver"]]:
        actor.set_password("Cuyes-local-test-123!")
        actor.save()
    env = {
        **os.environ, "SITRAP_TEST_API": live_server.url,
        "SITRAP_TEST_PEN": str(market["p1"].id), "SITRAP_TEST_CENTER": str(market["can"].id),
        "SITRAP_TEST_MODULE": str(market["module"].id), "SITRAP_TEST_POINT": str(market["point"].id),
        "SITRAP_TEST_DRIVER": str(market["driver"].id),
    }
    result = subprocess.run(
        ["npm.cmd" if os.name == "nt" else "npm", "exec", "playwright", "test", "--", "--config", "playwright.sales.config.ts"],
        cwd=Path(__file__).resolve().parent.parent / "frontend", env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=210,
    )
    assert result.returncode == 0, result.stdout + result.stderr
