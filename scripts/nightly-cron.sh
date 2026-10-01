#!/usr/bin/env bash
# zikai nightly (no_agent cron script): resync sitemaps -> incremental scrape ->
# rebuild mapping -> push data branch. Prints ONE line only when the corpus
# actually changed (delivered); silent otherwise (watchdog pattern: empty
# stdout sends nothing).
set -euo pipefail
cd /home/hermes/.hermes/work/zikai
export PATH=/home/hermes/.hermes/home/.local/bin:$PATH
LOG=data/nightly.log
.venv/bin/python -m zikai.cli nightly --push >>"$LOG" 2>&1
python3 - <<'EOF'
import hashlib, json, os, pathlib
os.chdir('/home/hermes/.hermes/work/zikai')
h = hashlib.sha256()
for f in ('data/corpus.json', 'data/decision_tree.json'):
    h.update(open(f, 'rb').read())
digest = h.hexdigest()[:16]
state = pathlib.Path('data/nightly.state')
prev = state.read_text().strip() if state.exists() else ''
if digest != prev:
    state.write_text(digest)
    c = json.load(open('data/corpus.json'))
    committed = os.popen('git log origin/data -1 --format=%h').read().strip()
    if prev:  # first run stays silent: nothing "changed"
        print(f"zikai nightly: corpus changed -> {len(c)} idioms, sha {digest}, pushed {committed}")
EOF
