# Uso: make <objetivo>. Asume .venv creado con `make setup`.
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
else
PY := .venv/bin/python
endif

.PHONY: setup dev-backend dev-frontend test data dataset train eval up down

setup:            ## Instala dependencias de Python y del frontend
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt
	cd frontend && npm install

dev-backend:      ## API en http://localhost:8000 (recarga automática)
	$(PY) -m uvicorn app.main:app --app-dir backend --reload --port 8000

dev-frontend:     ## UI en http://localhost:5173 (proxy /api → :8000)
	cd frontend && npm run dev

test:             ## Tests del backend y del pipeline
	$(PY) -m pytest -q

data:             ## S3 → bronze → silver → gold (Fase 2, rol A)
	$(PY) -m data_pipeline.run_pipeline --full

dataset:          ## Set de intenciones: ruido, split y validaciones (Fase 4.1, rol B)
	$(PY) -m ml.intent.build_dataset

train:            ## Clasificador de intención (Fase 4, rol B)
	$(PY) -m ml.intent.train

eval:             ## Evaluación end-to-end (Fase 6)
	$(PY) -m eval.runner

up:               ## Imagen completa con Docker
	docker compose up --build

down:
	docker compose down
