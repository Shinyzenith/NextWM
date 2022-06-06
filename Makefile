BINARY=next

all: run

run:
	@./$(BINARY)

clean:
	@rm -rf ./libnext/_libinput.*
	@rm -rf **/**/__pycache__
	@rm -rf .tox
	@rm -rf .mypy_cache

setup:
	@python3 -m pip install -r ./requirements.txt
	@python3 ./libnext/libinput_ffi_build.py

lint:
	@tox

.PHONY: run clean lint
