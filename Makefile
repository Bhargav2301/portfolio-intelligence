.PHONY: up down logs test check compile secrets

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

secrets:
	python scripts/bootstrap_env.py

compile:
	python -m compileall -q services/api/src services/agents/src scripts

test:
	python -m unittest discover -s services/api/tests -p "test_*.py" -v
	python -m unittest discover -s services/agents/tests -p "test_*.py" -v

check: compile test
	python scripts/verify_repository.py

