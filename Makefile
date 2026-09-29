# epson-esci is one executable Python file: no build step, no dependencies.
# The test suite needs no scanner, no root and no network.

TOOL := epson-esci

.PHONY: test check install clean

test:
	python3 tests/run-tests.py

check: test
	python3 -c "import ast; ast.parse(open('$(TOOL)').read()); print('$(TOOL): syntax ok')"

install:
	install -d $(DESTDIR)/usr/local/bin
	install -m 0755 $(TOOL) $(DESTDIR)/usr/local/bin/epson-esci

clean:
	rm -rf __pycache__ tests/__pycache__
	find . -name '*.pyc' -delete
