#!/bin/sh
# shim: ln -sf this file into .git/hooks/prepare-commit-msg
exec python3 "$(dirname "$(readlink -f "$0")")/zikai-prepare-commit-msg.py" "$@"
