# Deployment

Local:

```bash
python -m pip install -r requirements.txt
python scripts/init_platform.py
python scripts/run_api.py
```

Docker:

```bash
docker compose up --build
```

Health:

- `GET /health`
- `GET /api/health`

Production hardening still needed before real enterprise deployment:

- external managed database and vector store
- real secret manager
- SSO/RBAC/multi-tenant ACL
- OpenTelemetry/Prometheus/Grafana
- async task queue for large ingestion
