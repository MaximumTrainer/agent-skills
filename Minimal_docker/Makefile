.PHONY: all test shellcheck smoke check package clean

PYTHON ?= python3

all: check test shellcheck package

## Linter unit tests (stdlib only)
test:
	$(PYTHON) -m unittest discover -s tests -v

## Static analysis of the shell scripts
shellcheck:
	shellcheck scripts/inspect_image.sh tests/smoke/run.sh

## End-to-end build/run/inspect test (needs Docker)
smoke:
	bash tests/smoke/run.sh

## Validate SKILL.md frontmatter and file references
check:
	$(PYTHON) tools/package_skill.py --check

## Build dist/minimal-docker.skill
package:
	$(PYTHON) tools/package_skill.py dist

clean:
	rm -rf dist tests/__pycache__ scripts/__pycache__
