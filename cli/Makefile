check: lint

include ../python.mk

.PHONY: lint
lint: $(SITE_PACKAGES)
	flake8 src/**/*.py
