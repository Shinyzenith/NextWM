BINARY=next

all: dev

dev:
	@./$(BINARY)

setup:
	@python3 -m pip install -r ./requirements.txt

uninstall:
	@python3 -m pip uninstall -r ./requirements.txt

.PHONY: check dev setup uninstall
