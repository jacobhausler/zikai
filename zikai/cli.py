"""zikai CLI: build | nightly | serve | decide"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .config import REPO_ROOT, get_settings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zikai")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="records.jsonl -> corpus.json + decision_tree.json")
    b.add_argument("--records", default=str(REPO_ROOT / "data" / "records.jsonl"))
    b.add_argument("--out-dir", default=str(REPO_ROOT / "data"))

    n = sub.add_parser("nightly", help="resync slugs, scrape changed, rebuild, (optional) git push")
    n.add_argument("--push", action="store_true", help="git add/commit/push data artifacts on the current branch")
    n.add_argument("--force", action="store_true")

    s = sub.add_parser("serve", help="uvicorn the decisions API + dashboard")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8077)

    d = sub.add_parser("decide", help="one-off decision from the CLI")
    d.add_argument("text")
    d.add_argument("--level", default="compact")
    d.add_argument("--decider", default=None)
    d.add_argument("--trace", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "build":
        return _build(args)
    if args.cmd == "nightly":
        return _nightly(args)
    if args.cmd == "serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0
    if args.cmd == "decide":
        from .engine import load_engine
        out = load_engine(get_settings()).decide(args.text,
                                                 decider=args.decider,
                                                 trace=args.trace)
        from .shapes import hydrate
        out["idiom"] = hydrate(out["idiom"], level=args.level)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    return 2


def _build(args) -> int:
    from .tree import build_corpus, build_tree, load_records, save_json
    records = load_records(args.records)
    if not records:
        print(f"[build] no records in {args.records}", file=sys.stderr)
        return 1
    corpus = build_corpus(records)
    tree = build_tree(corpus)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    save_json(corpus, out / "corpus.json")
    save_json(tree, out / "decision_tree.json")
    sizes = {f: (out / f).stat().st_size for f in ("corpus.json", "decision_tree.json")}
    print(f"[build] {len(corpus)} idioms, {len(tree['clusters'])} clusters, "
          f"{len(tree['root']['options'])} themes -> {sizes}")
    return 0


def _nightly(args) -> int:
    py = sys.executable
    data = REPO_ROOT / "data"
    # 1. refresh slug list from sitemaps
    subprocess.run([py, str(REPO_ROOT / "pipeline" / "collect_slugs.py"),
                    "--out", str(data / "slugs.json")], check=True)
    # 2. scrape (incremental against last_seen.json unless --force)
    cmd = [py, str(REPO_ROOT / "pipeline" / "scrape.py"),
           "--slugs", str(data / "slugs.json"),
           "--out", str(data / "records.jsonl"),
           "--if-changed", str(data / "last_seen.json"),
           "--workers", "5"]
    if args.force:
        cmd.append("--force")
    subprocess.run(cmd, check=True)
    # 3. rebuild artifacts
    _build(argparse.Namespace(records=str(data / "records.jsonl"),
                              out_dir=str(data)))
    # 4. self-test the artifacts load and serve a decision
    from .engine import load_engine
    from .shapes import hydrate
    out = load_engine(get_settings()).decide("The team kept guessing without data.")
    assert out["idiom"]["slug"], "empty decision"
    print(f"[nightly] self-test pick: {hydrate(out['idiom'], level='text')}")
    # 5. optional git push (current branch; no --branch games: one branch,
    # honest history of mapping snapshots)
    if args.push:
        g = lambda *a: subprocess.run(["git", *a], cwd=REPO_ROOT, check=True)  # noqa: E731
        g("add", "data/corpus.json", "data/decision_tree.json",
          "data/records.jsonl", "data/slugs.json", "data/last_seen.json")
        r = subprocess.run(["git", "diff", "--cached", "--quiet"],
                           cwd=REPO_ROOT)
        if r.returncode == 0:
            print("[nightly] no data changes — nothing to push")
        else:
            from datetime import date
            g("commit", "-m", f"data: mapping snapshot {date.today().isoformat()}")
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT,
                capture_output=True, text=True).stdout.strip()
            g("push", "origin", branch)
            print(f"[nightly] pushed snapshot to origin/{branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
