#!/bin/bash
set -eux

rm -rf dist $HOME/.cache/aws_list_all/
python3.14 -m pip install --upgrade flake8 yapf pytest twine
python3.14 -m pip install -e .
aws_list_all --help
# Allow skipping tests during temporary runs by setting SKIP_TESTS=1 in the environment.
if [ -z "${SKIP_TESTS:-}" ]; then
	pytest
else
	echo "SKIP_TESTS is set; skipping pytest run"
fi
flake8
yapf -d -r aws_list_all/

rm -rf dist/
python -m build
twine check dist/*
twine upload dist/*
