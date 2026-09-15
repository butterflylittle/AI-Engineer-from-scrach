.PHONY: up down logs test migrate

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api worker web

test:
	docker compose run --rm api pytest -q /tests

migrate:
	docker compose run --rm api alembic upgrade head
