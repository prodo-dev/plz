SHELL := zsh -e -u

PYTHON_EXE = python3.6
PYTHON = $(shell command -v $(PYTHON_EXE) 2> /dev/null)
SITE_PACKAGES = env/lib/$(PYTHON_EXE)/site-packages

ifndef PYTHON
$(error "Could not find $(PYTHON_EXE).")
endif

$(SITE_PACKAGES): env requirements.txt
	pip install --requirement=requirements.txt
	touch $(SITE_PACKAGES)

.PHONY: freeze
freeze: env
	pip freeze > requirements.txt

env: $(PYTHON)
	virtualenv --python=$(PYTHON_EXE) env
	touch -t 197001010000 $(SITE_PACKAGES)
