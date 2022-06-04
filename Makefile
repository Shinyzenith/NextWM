BINARY=next

all: run

run:
	@./$(BINARY)

clean:
	@rm -rf ./libnext/_libinput.*
	@rm -rf **/**/__pycache__

setup:
	@python3 ./libnext/libinput_ffi_build.py

check:
	@#todo

.PHONY: run clean check
