$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
  python -c "from apps.api.main import app; assert app.title == 'Reality OS API Adapter'; assert len(app.routes) >= 20; print('[ok] api routes:', len(app.routes))"
  python -c "from services.supervisor import build_default_supervisor_snapshot; snapshot = build_default_supervisor_snapshot(); assert snapshot['tool_calls'][0]['execution_disabled'] is True; assert len(snapshot['approvals']) >= 1; print('[ok] supervisor dry-run snapshot')"
  @'
import os
from fastapi.testclient import TestClient

os.environ["REALITY_OS_API_AUTH_REQUIRED"] = "true"
os.environ.pop("REALITY_OS_API_KEY", None)
os.environ.pop("REALITY_OS_SERVER_API_KEY", None)
from apps.api.main import app

client = TestClient(app)
assert client.get("/sou/sources").status_code == 503
os.environ["REALITY_OS_API_KEY"] = "local-smoke-key"
assert client.get("/sou/sources", headers={"x-reality-os-api-key": "local-smoke-key"}).status_code == 400
ok = client.get(
    "/sou/sources",
    headers={"x-reality-os-api-key": "local-smoke-key", "x-tenant-id": "smoke-tenant"},
)
assert ok.status_code == 200, ok.text
secret_status = client.get(
    "/security/secret-status",
    headers={"x-reality-os-api-key": "local-smoke-key", "x-tenant-id": "smoke-tenant"},
)
assert secret_status.status_code == 200
body = secret_status.json()
assert body["server_only"] is True
assert body["values_exposed"] is False
print("[ok] production auth and server-only secret status")
'@ | python -
}
finally {
  Pop-Location
}
