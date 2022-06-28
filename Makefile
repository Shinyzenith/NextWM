BINARY=next

all: dev

dev:
	@./$(BINARY) -d

clean:
	@rm -rf ./libnext/_libinput.*
	@rm -rf **/**/__pycache__
	@rm -rf **/__pycache__
	@rm -rf .tox
	@rm -rf .eggs
	@rm -rf .mypy_cache

setup:
	@sudo python3 -m pip install -U -r ./requirements.txt
	@sudo python3 -m pip install -U -r ./requirements-optional.txt
	@python3 ./libnext/libinput_ffi_build.py

lint:
	@TOXENV=codestyle,flake,black,mypy,py310 tox

.PHONY: run clean lint
