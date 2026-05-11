# Latest fixes — proper folder structure

This branch holds all 31 files from `basu_test` at their exact VM
destination paths under `agentcore/`. Copy each file to the same path
on the client's VM.

## Work streams included

| Stream | Files |
|---|---|
| Dashboard KPI (Prometheus 429 fix) | `observability/otel_metrics.py`, `api/metrics_dashboard.py` |
| Outlook connector | `api/outlook_connector.py`, `components/tools/outlook_mail.py`, `services/outlook/graph_mail.py`, `pages/ConnectorsCatalogue/components/OutlookConnectorForm.tsx` |
| SharePoint connector | `api/sharepoint_connector.py`, `services/sharepoint/graph_sharepoint.py`, `components/tools/sharepoint_document.py`, `pages/ConnectorsCatalogue/components/SharePointCapabilityBanner.tsx` (NEW) |
| Teams connector | `api/teams.py`, `services/teams/{bot_handler,graph_api,service}.py`, `services/trigger/service.py`, frontend `teams-publish-modal.tsx` + 5 hook files + `types/teams/index.ts` |
| Foundation | `services/permissions/__init__.py` + `services/permissions/scope_check.py` (both NEW — create the directory first) |
| Connector catalogue | `api/connector_catalogue.py` |
| KB fix (Aman) | `api/files_user.py`, `services/database/models/file/model.py`, `alembic/versions/20260511_scope_file_name_unique_to_user_kb.py` (NEW migration) |
| Frontend package | `package.json`, `package-lock.json` |
| Page wiring | `pages/ConnectorsCatalogue/index.tsx` |

## Folders to create on VM

```
agentcore/src/backend/base/agentcore/services/permissions/
```

Then paste both `__init__.py` and `scope_check.py` into it.

All other files go into directories that already exist on the VM.

## After all 31 files are pasted

```bash
# Backend restart picks up new code
kubectl rollout restart deployment/<backend-deployment-name>

# Wait ~5 min so old high-cardinality Prometheus series age out
# of the [5m] rate window. After that the API Latency 429 stops.

# Frontend rebuild
cd agentcore/src/frontend && npm ci && npm run build
```

No Dockerfile, k8s YAML, ConfigMap or env-var changes required.
No new Python dependencies introduced.
