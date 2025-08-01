.PHONY: help build up down restart logs shell test migrate collectstatic clean

# Default target
help:
	@echo "Available commands:"
	@echo "  build          - Build Docker images"
	@echo "  up             - Start services in development mode"
	@echo "  up-prod        - Start services in production mode (with Nginx)"
	@echo "  down           - Stop and remove containers"
	@echo "  restart        - Restart services"
	@echo "  logs           - Show logs from all services"
	@echo "  logs-web       - Show logs from web service only"
	@echo "  shell          - Access Django shell in container"
	@echo "  bash           - Access bash shell in web container"
	@echo "  migrate        - Run Django migrations"
	@echo "  makemigrations - Create Django migrations"
	@echo "  collectstatic  - Collect static files"
	@echo "  test           - Run tests"
	@echo "  clean          - Remove all containers, volumes and images"
	@echo "  install        - Install Poetry dependencies locally"
	@echo "  lint           - Run code linting"
	@echo "  format         - Format code with black"

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Services started. Web available at http://localhost:8000"

up-prod:
	docker-compose --profile production up -d
	@echo "Production services started. Web available at http://localhost"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

# Django commands in container
shell:
	docker-compose exec web python manage.py shell

bash:
	docker-compose exec web bash

migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

# Testing
test:
	docker-compose exec web python manage.py test

test-coverage:
	docker-compose exec web coverage run --source='.' manage.py test
	docker-compose exec web coverage report
	docker-compose exec web coverage html

# Local development with Poetry
install:
	poetry install

install-dev:
	poetry install --with dev

run-local:
	poetry run python manage.py runserver

migrate-local:
	poetry run python manage.py migrate

shell-local:
	poetry run python manage.py shell

# Code quality
lint:
	poetry run flake8 .
	poetry run black --check .
	poetry run isort --check-only .

format:
	poetry run black .
	poetry run isort .

# Cleanup
clean:
	docker-compose down -v --rmi all --remove-orphans
	docker system prune -af

# Database operations
db-backup:
	docker-compose exec db mysqldump -u root -ppadel_password padel_db > backup_$$(date +%Y%m%d_%H%M%S).sql

db-restore:
	@read -p "Enter backup file path: " backup_file; \
	docker-compose exec -T db mysql -u root -ppadel_password padel_db < $$backup_file

# Development helpers
dev-setup: build up migrate collectstatic
	@echo "Development environment ready!"

prod-setup: build up-prod migrate collectstatic
	@echo "Production environment ready!"
