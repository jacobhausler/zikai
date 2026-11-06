"""Nightly sync must preserve remote work and retry already committed snapshots."""
import argparse
import subprocess
from types import SimpleNamespace

import pytest

from zikai import cli, engine, shapes


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          text=True, capture_output=True).stdout.strip()


@pytest.fixture
def nightly_repo(tmp_path, monkeypatch):
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True,
                   capture_output=True)
    repo = tmp_path / "nightly"
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True,
                   capture_output=True)
    git(repo, "config", "user.name", "Nightly test")
    git(repo, "config", "user.email", "nightly@example.invalid")
    (repo / "data").mkdir()
    for name in ("corpus.json", "decision_tree.json", "records.jsonl",
                 "slugs.json", "last_seen.json"):
        (repo / "data" / name).write_text("{}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    git(repo, "push", "origin", "HEAD:data")
    base = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(cli, "REPO_ROOT", repo)
    monkeypatch.setattr(cli, "_build", lambda args: 0)
    monkeypatch.setattr(cli, "get_settings", lambda: None)
    monkeypatch.setattr(engine, "load_engine", lambda settings: SimpleNamespace(
        decide=lambda text: {"idiom": {"slug": "test"}}))
    monkeypatch.setattr(shapes, "hydrate", lambda idiom, level: idiom)
    real_run = subprocess.run

    def only_git(argv, *args, **kwargs):
        if argv[0] == "git":
            return real_run(argv, *args, **kwargs)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", only_git)
    return repo, remote, base


def test_nightly_rebases_remote_before_push(nightly_repo, tmp_path):
    repo, remote, base = nightly_repo
    peer = tmp_path / "peer"
    subprocess.run(["git", "clone", "-b", "data", str(remote), str(peer)],
                   check=True, capture_output=True)
    git(peer, "config", "user.name", "Peer")
    git(peer, "config", "user.email", "peer@example.invalid")
    (peer / "README.md").write_text("remote work must survive\n")
    git(peer, "add", ".")
    git(peer, "commit", "-m", "remote advance")
    git(peer, "push", "origin", "data")
    (repo / "data" / "corpus.json").write_text('{"new": true}\n')
    assert cli._nightly(argparse.Namespace(push=True, force=False)) == 0
    assert git(remote, "rev-parse", "refs/heads/data") == git(repo, "rev-parse", "HEAD")
    assert (repo / "README.md").read_text() == "remote work must survive\n"
    assert git(repo, "status", "--porcelain") == ""


def test_nightly_retries_committed_snapshot_without_new_changes(nightly_repo):
    repo, remote, base = nightly_repo
    (repo / "data" / "corpus.json").write_text('{"pending": true}\n')
    git(repo, "add", "data/corpus.json")
    git(repo, "commit", "-m", "previously rejected snapshot")
    pending = git(repo, "rev-parse", "HEAD")
    assert cli._nightly(argparse.Namespace(push=True, force=False)) == 0
    assert git(remote, "rev-parse", "refs/heads/data") == pending


def test_nightly_does_not_hide_push_rejection(nightly_repo):
    repo, remote, base = nightly_repo
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    (repo / "data" / "corpus.json").write_text('{"rejected": true}\n')
    with pytest.raises(subprocess.CalledProcessError):
        cli._nightly(argparse.Namespace(push=True, force=False))
    assert git(remote, "rev-parse", "refs/heads/data") == base
