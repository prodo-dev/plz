PYTHON_EXE = python3.6
PYTHON = $(shell command -v $(PYTHON_EXE) 2> /dev/null)

ifndef PYTHON
$(error "Could not find $(PYTHON_EXE).")
endif

env: $(PYTHON)
	virtualenv --python=$(PYTHON_EXE) env
