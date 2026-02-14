.PHONY: install install-dev test clean

install:
	pip install .

install-dev:
	pip install -e ".[dev]"

test:
	python -m pytest test_kvenn.py -v

clean:
	rm -rf build dist *.egg-info __pycache__ kvenn/__pycache__ .pytest_cache
