PYTHON ?= python
PIP ?= $(PYTHON) -m pip

.PHONY: setup dev seed ingest eval test demo smoke docker desktop build-desktop smoke-test-rag

setup:
	$(PIP) install -r requirements.txt

dev:
	$(PYTHON) scripts/init_platform.py
	$(PYTHON) scripts/run_api.py

seed:
	$(PYTHON) scripts/seed_demo_data.py

ingest:
	$(PYTHON) scripts/ingest_docs.py --path data/sample_docs --replace

eval:
	$(PYTHON) scripts/run_eval.py --target all

test:
	$(PYTHON) -m pytest -q

demo:
	$(PYTHON) scripts/demo_all.py

smoke:
	$(PYTHON) scripts/smoke_test.py

desktop:
	$(PYTHON) scripts/run_desktop.py

build-desktop:
	$(PYTHON) scripts/build_desktop.py

smoke-test-rag:
	$(PYTHON) scripts/smoke_test_rag.py

docker:
	docker compose up --build
