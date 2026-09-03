#!/usr/bin/env sh
set -eu

forgegate_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
forgegate_python=${FORGEGATE_PYTHON:-python3.12}

cd "$forgegate_root"
if [ ! -x .venv/bin/python ]; then
    "$forgegate_python" -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check --upgrade \
    -c requirements/dev-constraints.txt pip
.venv/bin/python -m pip install --disable-pip-version-check \
    -c requirements/dev-constraints.txt -e ".[dev]"
.venv/bin/python tools/verify.py
