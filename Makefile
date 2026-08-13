.PHONY: test lint typecheck run

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

lint:
	ruff check .

typecheck:
	mypy src

run:
	uvicorn portfolio_intelligence.api.app:app --reload

