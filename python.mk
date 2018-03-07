SHELL := zsh -e -u

PYTHON_EXE = python3.6
PYTHON = $(shell command -v $(PYTHON_EXE) 2> /dev/null)
SITE_PACKAGES = env/lib/$(PYTHON_EXE)/site-packages

ifndef PYTHON
$(error "Could not find $(PYTHON_EXE).")
endif

$(SITE_PACKAGES): env requirements.txt
	./env/bin/pip install --requirement=requirements.txt
	touch $(SITE_PACKAGES)

.PHONY: upgrade-python-dependencies
upgrade-python-dependencies:
	packages=($$(pip list --outdated --format=json | jq -r '.[] | .name')); \
	if [[ $${#packages} -gt 0 ]]; then \
	  pip install --upgrade $${packages[@]}; \
	fi
	./env/bin/pip freeze | grep -v '^pkg-resources=' > requirements.txt

requirements.txt: env
	./env/bin/pip freeze | grep -v '^pkg-resources=' > requirements.txt

env:
	virtualenv --python=$(PYTHON_EXE) env
	touch -t 200001010000 $(SITE_PACKAGES)
