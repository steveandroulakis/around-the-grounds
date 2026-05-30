"""Integration tests for per-site ``skip_unchanged_deploys`` in the deploy path.

These exercise the real git flow in ``_deploy_with_github_auth`` against a local
bare repo standing in for the GitHub remote. GitHubAppAuth is faked and the
hardcoded ``authenticated_url`` is rewritten to the local bare repo path, so no
network or credentials are needed.

The behaviors pinned here:

- skip flag ON + unchanged events  -> volatile fields carried forward, deploy
  is a byte-identical no-op (no new commit), in BOTH root and subdir modes.
- skip flag ON + changed events     -> commit + push as normal.
- skip flag ON + brand-new empty repo (root mode) -> first deploy proceeds.
- skip flag OFF (Ballard)           -> never skips, even with identical events,
  so the hourly haiku/timestamp always deploys.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from around_the_grounds.main import _deploy_with_github_auth

# The exact URL _deploy_with_github_auth builds from the faked auth below.
AUTH_URL = "https://x-access-token:tok@github.com/owner/repo.git"
REPO_URL = "https://github.com/owner/repo.git"


def _make_bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    return remote


def _remote_head(remote: Path) -> Optional[str]:
    out = subprocess.run(
        ["git", "ls-remote", str(remote), "refs/heads/main"],
        capture_output=True,
        text=True,
    )
    return out.stdout.split()[0] if out.stdout.strip() else None


def _remote_file(tmp_path: Path, remote: Path, rel_path: str) -> Optional[dict]:
    co = tmp_path / "checkout"
    if co.exists():
        shutil.rmtree(co)
    subprocess.run(
        ["git", "clone", str(remote), str(co)], check=True, capture_output=True
    )
    f = co / rel_path
    return json.loads(f.read_text()) if f.exists() else None


def _run_deploy(
    cwd: Path,
    remote: Path,
    web_data: dict,
    template: str,
    deploy_subdir: str,
    skip: bool,
) -> bool:
    """Invoke _deploy_with_github_auth with auth faked and the remote redirected."""
    real_run = subprocess.run

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list):
            cmd = [str(remote) if x == AUTH_URL else x for x in cmd]
        return real_run(cmd, *args, **kwargs)

    fake_auth = MagicMock()
    fake_auth.get_access_token.return_value = "tok"
    fake_auth.repo_owner = "owner"
    fake_auth.repo_name = "repo"

    original_cwd = Path.cwd()
    try:
        os.chdir(cwd)
        with patch(
            "around_the_grounds.utils.github_auth.GitHubAppAuth",
            return_value=fake_auth,
        ), patch("around_the_grounds.main.subprocess.run", side_effect=fake_run):
            return _deploy_with_github_auth(
                web_data, REPO_URL, template, deploy_subdir, skip
            )
    finally:
        os.chdir(original_cwd)


def _make_cwd_with_template(tmp_path: Path, template: str) -> Path:
    cwd = tmp_path / "workdir"
    tdir = cwd / "public_templates" / template
    tdir.mkdir(parents=True)
    (tdir / "index.html").write_text("<html><body>template</body></html>")
    return cwd


def _web_data(
    events: list, updated: str, haiku: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "events": events,
        "updated": updated,
        "total_events": len(events),
        "site_name": "Test Site",
        "site_key": "test",
        "timezone": "America/New_York",
        "timezone_label": "ET",
        "timezone_note": "note",
        "errors": [],
        "haiku": haiku,
    }


E1 = [{"venue": "A", "title": "Show 1", "date": "2026-06-01"}]
E2 = [{"venue": "A", "title": "Show 2", "date": "2026-06-02"}]


OLD = "2026-05-01T00:00:00+00:00"
NEW = "2026-05-30T12:00:00+00:00"


class TestSkipUnchangedDeploys:
    def test_root_mode_skip_on_unchanged_events_is_noop(self, tmp_path: Path) -> None:
        """Root mode + skip + identical events -> no new commit (the key new capability)."""
        remote = _make_bare_remote(tmp_path)
        cwd = _make_cwd_with_template(tmp_path, "kids")
        # Prior deploy seeds the remote exactly as production would (template +
        # data.json) with an OLD timestamp.
        _run_deploy(cwd, remote, _web_data(E1, OLD), "kids", "", skip=True)
        head_before = _remote_head(remote)

        # Same events, a fresh timestamp: must carry OLD forward and skip.
        result = _run_deploy(cwd, remote, _web_data(E1, NEW), "kids", "", skip=True)

        assert result is True
        assert _remote_head(remote) == head_before, "no-op deploy must not add a commit"

    def test_root_mode_skip_on_changed_events_deploys(self, tmp_path: Path) -> None:
        """Root mode + skip + changed events -> commit + push."""
        remote = _make_bare_remote(tmp_path)
        cwd = _make_cwd_with_template(tmp_path, "kids")
        _run_deploy(cwd, remote, _web_data(E1, OLD), "kids", "", skip=True)
        head_before = _remote_head(remote)

        result = _run_deploy(cwd, remote, _web_data(E2, NEW), "kids", "", skip=True)

        assert result is True
        assert _remote_head(remote) != head_before, "changed events must push a commit"
        deployed = _remote_file(tmp_path, remote, "data.json")
        assert deployed is not None and deployed["events"] == E2

    def test_skip_still_deploys_template_change_with_unchanged_events(
        self, tmp_path: Path
    ) -> None:
        """skip ON + same events but a changed template (index.html) -> still deploys.

        The skip is meant to suppress only no-op runs; a real template/CSS change
        must still go out even when the event set is identical.
        """
        remote = _make_bare_remote(tmp_path)
        cwd = _make_cwd_with_template(tmp_path, "kids")
        _run_deploy(cwd, remote, _web_data(E1, OLD), "kids", "", skip=True)
        head_before = _remote_head(remote)

        # Edit the template; events stay identical.
        (cwd / "public_templates" / "kids" / "index.html").write_text(
            "<html><body>NEW TEMPLATE</body></html>"
        )
        result = _run_deploy(cwd, remote, _web_data(E1, NEW), "kids", "", skip=True)

        assert result is True
        assert _remote_head(remote) != head_before, "template change must deploy"

    def test_root_mode_skip_first_deploy_to_empty_repo(self, tmp_path: Path) -> None:
        """Root mode + skip against an empty repo -> first deploy proceeds (no baseline)."""
        remote = _make_bare_remote(tmp_path)  # empty: no main branch yet
        assert _remote_head(remote) is None

        cwd = _make_cwd_with_template(tmp_path, "kids")
        result = _run_deploy(cwd, remote, _web_data(E1, NEW), "kids", "", skip=True)

        assert result is True
        deployed = _remote_file(tmp_path, remote, "data.json")
        assert deployed is not None and deployed["events"] == E1

    def test_subdir_mode_skip_on_unchanged_events_is_noop(self, tmp_path: Path) -> None:
        """Subdir mode + skip + identical events -> no new commit."""
        remote = _make_bare_remote(tmp_path)
        cwd = _make_cwd_with_template(tmp_path, "food-trucks")
        _run_deploy(cwd, remote, _web_data(E1, OLD), "food-trucks", "public", skip=True)
        head_before = _remote_head(remote)

        result = _run_deploy(
            cwd, remote, _web_data(E1, NEW), "food-trucks", "public", skip=True
        )

        assert result is True
        assert _remote_head(remote) == head_before, "no-op deploy must not add a commit"

    def test_subdir_mode_skip_off_always_deploys(self, tmp_path: Path) -> None:
        """Ballard case: skip OFF + identical events still deploys the fresh haiku/timestamp."""
        remote = _make_bare_remote(tmp_path)
        cwd = _make_cwd_with_template(tmp_path, "food-trucks")
        _run_deploy(
            cwd,
            remote,
            _web_data(E1, OLD, haiku="old haiku"),
            "food-trucks",
            "public",
            skip=False,
        )
        head_before = _remote_head(remote)

        new = _web_data(E1, NEW, haiku="fresh hourly haiku")
        result = _run_deploy(cwd, remote, new, "food-trucks", "public", skip=False)

        assert result is True
        assert _remote_head(remote) != head_before, "skip OFF must always commit"
        deployed = _remote_file(tmp_path, remote, "public/data.json")
        assert deployed is not None
        assert deployed["updated"] == NEW
        assert deployed["haiku"] == "fresh hourly haiku"
