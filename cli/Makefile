check: test lint

include ../python.mk

.PHONY: test
test: $(SITE_PACKAGES)
	./env/bin/nosetests

.PHONY: lint
lint: $(SITE_PACKAGES)
	./env/bin/flake8 src/**/*.py
