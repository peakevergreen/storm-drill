PYTHON ?= python3
.DEFAULT_GOAL := help

.PHONY: help list scripts demo burst test lint
help:
	@printf '%s\n' 'make list     List the call scenarios' 'make scripts  Print every call script for a tester' 'make demo     Score the two bundled example runs' 'make burst    Plan 20 calls in 10 minutes' 'make test     Run the tests' 'make lint     Run Ruff (install ruff first)'

list:
	$(PYTHON) -m stormdrill list

scripts:
	$(PYTHON) -m stormdrill script

demo:
	$(PYTHON) -m stormdrill score examples/good-agent
	$(PYTHON) -m stormdrill score examples/weak-agent

burst:
	$(PYTHON) -m stormdrill burst --calls 20 --minutes 10 --lines 4

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	ruff check .
