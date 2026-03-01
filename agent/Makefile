VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

.PHONY: install install-dev up down reset logs shell tables seed status serve finetune finetune-db finetune-fast clean help

help: ## Show all commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36mmake %-14s\033[0m %s\n", $$1, $$2}'

# ── Python ──────────────────────────────────────────────────────

venv:
	python3 -m venv $(VENV)

install: venv ## Create .venv + install all dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	@echo "Done. Activate with: source $(VENV)/bin/activate"

install-dev: venv ## Create .venv + install with dev tools
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

# ── Database ────────────────────────────────────────────────────

up: ## Start MySQL container
	sudo docker compose up -d
	@echo "Waiting for MySQL..."
	@until sudo docker exec store_142_db mysqladmin ping -h localhost --silent 2>/dev/null; do sleep 1; done
	@echo "MySQL ready on localhost:3306"

down: ## Stop and remove container
	sudo docker compose down

reset: ## Nuke everything and start fresh
	sudo docker compose down
	sudo docker compose up -d
	@echo "Waiting for MySQL..."
	@until sudo docker exec store_142_db mysqladmin ping -h localhost --silent 2>/dev/null; do sleep 1; done
	@echo "Clean slate ready"

logs: ## Tail MySQL logs
	sudo docker compose logs -f mysql

shell: ## Open MySQL shell
	sudo docker exec -it store_142_db mysql -u root -pretailagent store_142

tables: ## List all tables
	@sudo docker exec store_142_db mysql -u root -pretailagent store_142 -e "SHOW TABLES;"

status: ## Show row counts for all tables
	@sudo docker exec store_142_db mysql -u root -pretailagent store_142 -e " \
		SELECT 'vendors' AS tbl, COUNT(*) AS rows FROM vendors UNION ALL \
		SELECT 'inventory', COUNT(*) FROM inventory UNION ALL \
		SELECT 'cameras', COUNT(*) FROM cameras UNION ALL \
		SELECT 'camera_product_map', COUNT(*) FROM camera_product_map UNION ALL \
		SELECT 'workers', COUNT(*) FROM workers UNION ALL \
		SELECT 'managers', COUNT(*) FROM managers UNION ALL \
		SELECT 'tickets', COUNT(*) FROM tickets UNION ALL \
		SELECT 'vendor_orders', COUNT(*) FROM vendor_orders UNION ALL \
		SELECT 'vision_events', COUNT(*) FROM vision_events UNION ALL \
		SELECT 'agent_log', COUNT(*) FROM agent_log;"

seed: ## Re-run init.sql without restarting container
	sudo docker exec -i store_142_db mysql -u root -pretailagent < init.sql
	@echo "Database re-seeded"

# ── Server ──────────────────────────────────────────────────────

serve: ## Start the FastAPI agent server
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

# ── Fine-tuning ─────────────────────────────────────────────────

finetune: ## Fine-tune FunctionGemma on seed examples (~30-45 min)
	$(PYTHON) finetune.py

finetune-db: ## Fine-tune on seed + real decisions from MySQL
	$(PYTHON) finetune.py --from-db --host localhost --db store_142

finetune-fast: ## Quick fine-tune (5 epochs, for testing)
	$(PYTHON) finetune.py --epochs 5

# ── Cleanup ─────────────────────────────────────────────────────

clean: ## Remove .venv and all caches
	rm -rf $(VENV) __pycache__ *.egg-info .pytest_cache
	@echo "Cleaned"
