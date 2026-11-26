import os
import subprocess
from pathlib import Path

import pytest

from apps.accounts.models import User
from tests.test_access import assign
from tests.test_cuyes import farm, item, send  # noqa: F401


@pytest.mark.skipif(os.environ.get("SITRAP_BROWSER_TESTS") != "1", reason="Requires Playwright")
@pytest.mark.django_db(transaction=True)
def test_direction_real_browser(live_server, farm):  # noqa: F811
    director = User.objects.create_user(username="direccion-prueba", password="Director-test-2026!")
    assign(director, "DIRECTOR")
    send(farm["worker"], "OPEN", pen_id=str(farm["p1"].id), lot={"provenance": "Prueba"},
         items=[item(category="MACHO", quantity=10)])
    result = subprocess.run(
        ["npm.cmd" if os.name == "nt" else "npm", "exec", "playwright", "test", "--",
         "--config", "playwright.direction.config.ts"],
        cwd=Path(__file__).resolve().parent.parent / "frontend",
        env={**os.environ, "SITRAP_TEST_API": live_server.url, "SITRAP_DIRECTION_CENTER": str(farm["can"].id)},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
