.PHONY: help tests prepare clean version name install_poetry
help:
	@echo "Help"
	@echo "----"
	@echo
	@echo "  tests - run all tests like CI does"
	@echo "  linters - run just linters"
	@echo "  pytest - run just pytest"
	@echo "  install_hooks - install pre-commit hook"
	@echo "  generate_requirements - save non-dev requirements from poetry to requirements.txt"
	@echo "  diagrams - generate diagrams from docs/digrams folder from mermaid files to svg"

tests:
	docker compose run --rm app ./docker/ci.sh && docker compose down -v || (docker compose down -v; exit 1)

linters:
	poetry run ./docker/ci.sh --action=formatters && poetry run ./docker/ci.sh --action=linters

pytest:
	docker compose build app && docker compose run --rm app poetry run pytest && docker compose down -v || (docker compose down -v; exit 1)

init_development:
	@poetry run pre-commit install --install-hooks
	@cp ./config/.env.template ./config/.env
	@cp docker-compose.override.yml.template docker-compose.override.yml

generate_requirements:
	@poetry export --only=main --without-hashes > requirements.txt

diagrams:
	@FILES=$$(find ./docs/diagrams -type f -name "*.mmd"); \
	if [ -z "$$FILES" ]; then \
		echo "No diagrams to generate"; \
	else \
		bash generate_diagrams.sh $$FILES && echo "No new diagrams" || echo "Diagrams generated"; \
	fi
