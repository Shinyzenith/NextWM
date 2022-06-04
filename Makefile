BINARY=next

all: run

run:
	@./$(BINARY)

clean:
	@rm -rf ./libnext/_libinput.*
	@rm -rf **/**/__pycache__

setup:
	@python3 -m pip install -r ./requirements.txt
	@python3 ./libnext/libinput_ffi_build.py

lint:
	@TOXENV=codestyle,pep8,mypy tox

.PHONY: run clean lint
