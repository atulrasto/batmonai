.PHONY: up down logs migrate seed shell-db shell-api lint fmt pre-commit help \
        prod-up prod-down prod-logs prod-migrate prod-seed backup restore

COMPOSE      = docker compose
COMPOSE_PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml
ENV_FILE     = .env

# ── Dev lifecycle ──────────────────────────────────────────────────────────────

up: ## Start all services (build if needed)
	$(COMPOSE) up -d --build

down: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) down

down-v: ## Stop containers AND remove volumes (destructive!)
	$(COMPOSE) down -v

logs: ## Tail logs for all services (Ctrl-C to stop)
	$(COMPOSE) logs -f

logs-%: ## Tail logs for a specific service, e.g. make logs-api
	$(COMPOSE) logs -f $*

restart-%: ## Restart a specific service, e.g. make restart-api
	$(COMPOSE) restart $*

# ── Migrations ────────────────────────────────────────────────────────────────

migrate: ## Run alembic upgrade head inside the migrate container
	$(COMPOSE) run --rm migrate alembic upgrade head

migrate-down: ## Roll back one migration
	$(COMPOSE) run --rm migrate alembic downgrade -1

migrate-history: ## Show migration history
	$(COMPOSE) run --rm migrate alembic history --verbose

migrate-new: ## Create a new migration; usage: make migrate-new MSG="add foo table"
	$(COMPOSE) run --rm migrate alembic revision --autogenerate -m "$(MSG)"

# ── Seeding ───────────────────────────────────────────────────────────────────

seed: ## Seed superuser from .env (SUPERUSER_EMAIL / SUPERUSER_PASSWORD)
	$(COMPOSE) run --rm api python -m app.cli

# ── Shell access ──────────────────────────────────────────────────────────────

shell-db: ## psql into the postgres container
	$(COMPOSE) exec postgres psql -U $$(grep POSTGRES_USER $(ENV_FILE) | cut -d= -f2) -d $$(grep POSTGRES_DB $(ENV_FILE) | cut -d= -f2)

shell-api: ## bash into the api container
	$(COMPOSE) exec api bash

shell-ingestion: ## bash into the ingestion container
	$(COMPOSE) exec ingestion bash

# ── Code quality ──────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check backend/ ingestion/ tools/

fmt: ## Auto-format with ruff + black
	ruff format backend/ ingestion/ tools/
	black backend/ ingestion/ tools/

pre-commit: ## Run all pre-commit hooks against staged files
	pre-commit run --all-files

# ── Dev TLS certs ─────────────────────────────────────────────────────────────

gen-certs: ## Generate dev TLS certs for Mosquitto (one-time; skips if already exist)
	@if [ -f mosquitto/certs/ca.crt ]; then \
		echo "Dev certs already exist in mosquitto/certs/ — delete to regenerate."; \
	else \
		bash tools/gen-dev-certs.sh; \
	fi

# ── Mosquitto helpers ─────────────────────────────────────────────────────────

mqtt-passwd: ## Add/update a device password (live container); usage: make mqtt-passwd USER=appliance1
	$(COMPOSE) exec mosquitto mosquitto_passwd /mosquitto/config/passwd $(USER)

# ── Simulation ────────────────────────────────────────────────────────────────

sim: ## Run sim_publisher against local plain broker; override with APPLIANCE=uid BATTERIES=uid CHANNEL=uid INTERVAL=10
	python tools/sim_publisher.py \
		--appliance-uid "$(or $(APPLIANCE),test-appliance-001)" \
		--battery-uids "$(or $(BATTERIES),test-battery-001)" \
		--channel-uids "$(or $(CHANNEL),test-channel-001)" \
		--broker localhost --port 1884 --interval $(or $(INTERVAL),10)

sim-tls: ## Run sim_publisher over TLS; set APPLIANCE, USER, PASS in .env or env
	python tools/sim_publisher.py \
		--appliance-uid "$(or $(APPLIANCE),test-appliance-001)" \
		--battery-uids "$(or $(BATTERIES),test-battery-001)" \
		--channel-uids "$(or $(CHANNEL),test-channel-001)" \
		--broker localhost --port 8883 --interval $(or $(INTERVAL),10) \
		--tls --ca-cert mosquitto/certs/ca.crt \
		--username "$(USER)" --password "$(PASS)"

# ── Firmware ──────────────────────────────────────────────────────────────────

firmware-build: ## Build firmware with PlatformIO; usage: make firmware-build VER=1.0.0
	cd firmware && pio run
	$(eval VER ?= $(shell grep 'FW_VERSION' firmware/include/config.h | cut -d'"' -f2))
	mkdir -p firmware_profiles/v$(VER)
	cp firmware/.pio/build/esp32dev/bootloader.bin  firmware_profiles/v$(VER)/
	cp firmware/.pio/build/esp32dev/partitions.bin  firmware_profiles/v$(VER)/
	cp firmware/.pio/build/esp32dev/firmware.bin    firmware_profiles/v$(VER)/
	@echo "Binaries copied to firmware_profiles/v$(VER)/"
	@echo "Update firmware_profiles/v$(VER)/manifest.json built_at timestamp."

firmware-flash: ## Flash directly via USB; usage: make firmware-flash PORT=/dev/ttyUSB0
	cd firmware && pio run -t upload --upload-port $(or $(PORT),auto)

# ── Production lifecycle ───────────────────────────────────────────────────────

prod-up: ## Start all services in PRODUCTION mode (build + pull latest)
	$(COMPOSE_PROD) pull --ignore-pull-failures || true
	$(COMPOSE_PROD) up -d --build

prod-down: ## Stop production containers (keeps volumes)
	$(COMPOSE_PROD) down

prod-logs: ## Tail production logs (Ctrl-C to stop)
	$(COMPOSE_PROD) logs -f

prod-migrate: ## Run migrations in production
	$(COMPOSE_PROD) run --rm migrate alembic upgrade head

prod-seed: ## Seed superuser in production
	$(COMPOSE_PROD) run --rm api python -m app.cli

# ── Backup / restore ───────────────────────────────────────────────────────────

backup: ## Trigger an immediate pg_dump (prod); output in ./backups/
	$(COMPOSE_PROD) run --rm backup sh /backup.sh

restore: ## Restore latest dump; usage: make restore FILE=backups/batmonai_YYYYMMDD_HHMMSS.dump
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/batmonai_...dump" && exit 1)
	$(COMPOSE_PROD) exec postgres pg_restore \
	  --clean --if-exists --no-owner --no-acl \
	  -U $$(grep POSTGRES_USER $(ENV_FILE) | cut -d= -f2) \
	  -d $$(grep POSTGRES_DB   $(ENV_FILE) | cut -d= -f2) \
	  /$(FILE)

# ── Help ──────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_%-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
