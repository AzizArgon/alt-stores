"""_local (price lists, DB copies, server passwords) stays outside git: ignored and never in the index."""

import shutil
import subprocess

import pytest

from app.core.config import BACKEND_DIR, LOCAL_DIR

REPO = BACKEND_DIR.parent
pytestmark = pytest.mark.skipif(not (REPO / ".git").exists() or not shutil.which("git"), reason="needs the git repo")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def test_local_dir_is_ignored():
    for path in ("_local/", "_local/secrets/server_passwords.txt", "_local/backups/server/x.db"):
        assert git("check-ignore", "-q", path).returncode == 0, path


def test_no_local_files_in_index():
    assert git("ls-files", "--", "_local").stdout == ""
    assert git("ls-files", "--", LOCAL_DIR.as_posix()).stdout == ""
