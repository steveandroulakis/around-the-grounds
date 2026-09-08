"""Browser-level checks for the per-site templates.

Runs tests/browser/check_templates.mjs in a real Chromium via Playwright
(Node). The script serves each template with a hostile data.json and asserts
scraped strings render as text, search/filter interactions keep the original
names, and calendar-date headings are stable across visitor timezones.

Skipped when Node or the Playwright package is unavailable.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tests" / "browser" / "check_templates.mjs"
TEMPLATES = REPO_ROOT / "public_templates"


def _node_env() -> dict:
    env = dict(os.environ)
    try:
        global_root = subprocess.run(
            ["npm", "root", "-g"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        global_root = ""
    if global_root:
        existing = env.get("NODE_PATH", "")
        env["NODE_PATH"] = (
            f"{global_root}{os.pathsep}{existing}" if existing else global_root
        )
    return env


def _playwright_available() -> bool:
    if shutil.which("node") is None:
        return False
    probe = subprocess.run(
        ["node", "-e", "require('playwright')"],
        capture_output=True,
        env=_node_env(),
    )
    return probe.returncode == 0


@pytest.mark.integration
@pytest.mark.skipif(
    not _playwright_available(), reason="Node + Playwright not available"
)
def test_templates_render_hostile_data_as_text() -> None:
    result = subprocess.run(
        ["node", str(SCRIPT), str(TEMPLATES)],
        capture_output=True,
        text=True,
        env=_node_env(),
        timeout=180,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    for template in ("food-trucks", "music", "kids"):
        assert f"{template}: ok" in result.stdout
