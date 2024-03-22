lint: clean
	- pip install ruff codespell -q
	- ruff check --fix zs/
	- codespell

format:
	- pip install ruff -q
	- ruff format zs/

test: lint
	py.test -vvv --cov zs --cov-report term-missing --cov-report xml:cobertura.xml --junitxml=testresult.xml tests

clean:
	- find . -iname "*__pycache__" | xargs rm -rf
	- find . -iname "*.pyc" | xargs rm -rf
	- rm cobertura.xml -f
	- rm testresult.xml -f
	- rm .coverage -f
	- rm .pytest_cache/ -rf

lock-requirements:
	- pip install pip-tools -q
	- pip-compile -o requirements.txt

deps: lock-requirements
	- pip-sync

venv:
	- virtualenv --python=$(shell which python3) --prompt '<venv:zs>' venv
