.DEFAULT_GOAL := run

PYTHON := .venv/bin/python
SYSTEM_PYTHON ?= python3.12

.venv/.installed: pyproject.toml
	$(SYSTEM_PYTHON) -m venv .venv
	$(PYTHON) -m pip install -e .
	touch $@

install: .venv/.installed

run: .venv/.installed
	$(PYTHON) src/main.py $(ARGS)

test: .venv/.installed
	$(PYTHON) -m unittest discover -s src

clean:
	rm -rf .venv *.egg-info build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

.PHONY: install run test clean
