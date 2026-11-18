"""Git-based development update synchronization for ParseCraft.

This is a developer workflow helper: it compares the local checkout against
``origin/main`` and pulls changes on request. It never downloads or replaces
executables.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional

from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GitStatus:
    available: bool
    repo: bool
    branch: str = ""
    local_commit: str = ""
    remote_commit: str = ""
    dirty: bool = False
    error: str = ""

    @property
    def update_available(self) -> bool:
        return (self.available and self.repo and self.local_commit and
                self.remote_commit and self.local_commit != self.remote_commit)


class GitUpdater:
    def __init__(self, root: Optional[str] = None) -> None:
        self.root = root or os.getcwd()

    def _run(self, *args) -> tuple[int, str, str]:
        try:
            p = subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except FileNotFoundError:
            return 127, "", "git not found"
        except Exception as exc:  # noqa: BLE001
            return 1, "", str(exc)

    def is_git_available(self) -> bool:
        rc, _, _ = self._run("--version")
        return rc == 0

    def is_repo(self) -> bool:
        rc, out, _ = self._run("rev-parse", "--is-inside-work-tree")
        return rc == 0 and out == "true"

    def current_branch(self) -> str:
        rc, out, _ = self._run("branch", "--show-current")
        return out if rc == 0 else ""

    def head_commit(self) -> str:
        rc, out, _ = self._run("rev-parse", "HEAD")
        return out[:7] if rc == 0 else ""

    def fetch(self) -> tuple[bool, str]:
        rc, out, err = self._run("fetch", "origin")
        if rc != 0:
            return False, err or out
        return True, ""

    def remote_commit(self, branch: str = "main") -> str:
        rc, out, _ = self._run("rev-parse", f"origin/{branch}")
        return out[:7] if rc == 0 else ""

    def is_dirty(self) -> bool:
        rc, out, _ = self._run("status", "--porcelain")
        return rc == 0 and bool(out.strip())

    def status(self) -> GitStatus:
        if not self.is_git_available():
            return GitStatus(available=False, repo=False, error="Git not installed")
        if not self.is_repo():
            return GitStatus(available=True, repo=False, error="Not a git repository")
        branch = self.current_branch() or "main"
        local = self.head_commit()
        dirty = self.is_dirty()
        ok, err = self.fetch()
        if not ok:
            return GitStatus(available=True, repo=True, branch=branch,
                             local_commit=local, dirty=dirty, error=err)
        remote = self.remote_commit(branch)
        return GitStatus(available=True, repo=True, branch=branch,
                         local_commit=local, remote_commit=remote, dirty=dirty)

    def pull(self, branch: str = "main") -> tuple[bool, str]:
        if self.is_dirty():
            return False, "Local changes detected. Commit or stash before updating."
        rc, out, err = self._run("pull", "origin", branch)
        if rc != 0:
            return False, err or out
        return True, out
