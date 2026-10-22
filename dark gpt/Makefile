# Comandi di sviluppo DarkGPT.
# Su Windows usare `make` se disponibile, oppure i comandi equivalenti
# indicati nel README.

PYTHON ?= .venv/Scripts/python.exe
PIP    ?= .venv/Scripts/python.exe -m pip
NPM    ?= npm

.PHONY: help install install-backend install-frontend test test-backend test-lab \
        validate-cvss dev-backend dev-frontend dev-lab clean

help: ## Mostra questo aiuto
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Installa tutte le dipendenze

install-backend: ## Crea il venv e installa le dipendenze Python
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt

install-frontend: ## Installa le dipendenze Node
	cd frontend && $(NPM) install

test: ## Esegue l'intera suite (backend + laboratorio)
	$(PYTHON) scripts/run_tests.py

test-backend: ## Esegue solo i test del backend
	cd backend && ../$(PYTHON) -m pytest -q

test-lab: ## Esegue solo i test del laboratorio
	$(PYTHON) -m pytest lab/tests -q

validate-cvss: ## Valida il calcolo CVSS su tutti i vettori base
	$(PYTHON) scripts/validate_cvss.py

dev-backend: ## Avvia il backend su 127.0.0.1:8000
	$(PYTHON) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

dev-frontend: ## Avvia la dashboard su localhost:3000
	cd frontend && $(NPM) run dev

dev-lab: ## Avvia il bersaglio vulnerabile del laboratorio su 127.0.0.1:8100
	$(PYTHON) -m uvicorn lab.sqli_app.vulnerable:app --host 127.0.0.1 --port 8100

clean: ## Rimuove artefatti e cache
	rm -rf frontend/.next frontend/node_modules .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
