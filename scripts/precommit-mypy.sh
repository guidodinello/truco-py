#!/usr/bin/env bash
# Pre-commit mypy hook. Runs mypy with the project venv's interpreter so gamekit /
# stable_baselines3 / torch resolve (a mypy without them silently hides real errors).
#
# Deliberately not `uv run`: in a git worktree there is no .venv, and `uv run` would
# build a partial one on the (full) main disk. The venv lives on an external HDD and is
# symlinked as .venv in the main checkout, so worktrees borrow it from there with
# PYTHONPATH pointing at the worktree (the venv's editable install points at the main
# checkout, which would otherwise be what gets type-checked).
set -euo pipefail

top=$(git rev-parse --show-toplevel)
common=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")

for root in "$top" "$common"; do
    if [[ -x "$root/.venv/bin/python" ]]; then
        py="$root/.venv/bin/python"
        break
    fi
done
if [[ -z "${py:-}" ]]; then
    echo "precommit-mypy: no .venv/bin/python in $top or $common (see CLAUDE.md)" >&2
    exit 1
fi

cd "$top"
PYTHONPATH="$top${PYTHONPATH:+:$PYTHONPATH}" exec "$py" -m mypy .
