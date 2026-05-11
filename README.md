# Original-name files — VM destination map

Each file in this folder has its original basename from the codebase
(e.g. `outlook_connector.py`, not the long encoded version).
Two `service.py` files exist (one in Teams, one in trigger) so they
live under `teams/` and `trigger/` subfolders here to avoid collision —
on the VM they go to the paths shown below.

## Map: file in this folder → VM destination path

### Backend Python (16)

| File here | VM path |
|---|---|
| `connector_catalogue.py` | `agentcore/src/backend/base/agentcore/api/connector_catalogue.py` |
| `metrics_dashboard.py` | `agentcore/src/backend/base/agentcore/api/metrics_dashboard.py` |
| `outlook_connector.py` | `agentcore/src/backend/base/agentcore/api/outlook_connector.py` |
| `sharepoint_connector.py` | `agentcore/src/backend/base/agentcore/api/sharepoint_connector.py` |
| `teams.py` | `agentcore/src/backend/base/agentcore/api/teams.py` |
| `outlook_mail.py` | `agentcore/src/backend/base/agentcore/components/tools/outlook_mail.py` |
| `sharepoint_document.py` | `agentcore/src/backend/base/agentcore/components/tools/sharepoint_document.py` |
| `otel_metrics.py` | `agentcore/src/backend/base/agentcore/observability/otel_metrics.py` |
| `graph_mail.py` | `agentcore/src/backend/base/agentcore/services/outlook/graph_mail.py` |
| `__init__.py` | `agentcore/src/backend/base/agentcore/services/permissions/__init__.py` **[NEW dir]** |
| `scope_check.py` | `agentcore/src/backend/base/agentcore/services/permissions/scope_check.py` **[NEW]** |
| `graph_sharepoint.py` | `agentcore/src/backend/base/agentcore/services/sharepoint/graph_sharepoint.py` |
| `bot_handler.py` | `agentcore/src/backend/base/agentcore/services/teams/bot_handler.py` |
| `graph_api.py` | `agentcore/src/backend/base/agentcore/services/teams/graph_api.py` |
| `teams/service.py` | `agentcore/src/backend/base/agentcore/services/teams/service.py` |
| `trigger/service.py` | `agentcore/src/backend/base/agentcore/services/trigger/service.py` |

### Frontend (12)

| File here | VM path |
|---|---|
| `package.json` | `agentcore/src/frontend/package.json` |
| `package-lock.json` | `agentcore/src/frontend/package-lock.json` |
| `teams-publish-modal.tsx` | `agentcore/src/frontend/src/components/core/agentToolbarComponent/components/teams/teams-publish-modal.tsx` |
| `use-delete-unpublish-from-teams.ts` | `agentcore/src/frontend/src/controllers/API/queries/teams/use-delete-unpublish-from-teams.ts` |
| `use-get-teams-oauth-status.ts` | `agentcore/src/frontend/src/controllers/API/queries/teams/use-get-teams-oauth-status.ts` |
| `use-get-teams-status.ts` | `agentcore/src/frontend/src/controllers/API/queries/teams/use-get-teams-status.ts` |
| `use-post-publish-to-teams.ts` | `agentcore/src/frontend/src/controllers/API/queries/teams/use-post-publish-to-teams.ts` |
| `use-post-sync-teams-app.ts` | `agentcore/src/frontend/src/controllers/API/queries/teams/use-post-sync-teams-app.ts` |
| `OutlookConnectorForm.tsx` | `agentcore/src/frontend/src/pages/ConnectorsCatalogue/components/OutlookConnectorForm.tsx` |
| `SharePointCapabilityBanner.tsx` | `agentcore/src/frontend/src/pages/ConnectorsCatalogue/components/SharePointCapabilityBanner.tsx` **[NEW]** |
| `index.tsx` | `agentcore/src/frontend/src/pages/ConnectorsCatalogue/index.tsx` |
| `index.ts` | `agentcore/src/frontend/src/types/teams/index.ts` |

## Notes on duplicates / clashes

* **Two `service.py` files** — the Teams adapter service and the
  Trigger scanner service share the same basename in the codebase. To
  keep both with their original names, this folder uses one-level
  subdirs: `teams/service.py` and `trigger/service.py`. When copying,
  remember which one goes to which VM directory.
* **`index.tsx` vs `index.ts`** — different file extensions, both fine
  in the same flat folder. The `.tsx` is the ConnectorsCatalogue page;
  the `.ts` is the Teams types module.
* **`__init__.py`** — only one in your changeset (the new
  `services/permissions/` package). Make the directory on the VM
  before pasting both `__init__.py` and `scope_check.py` into it.

## Companion folder

The parent folder
(`~/Downloads/teams-sharepoint-outlook-readonlyFix/`) holds the same
28 files with their full VM path encoded into each filename (`__`
separates directory levels). Use whichever style you prefer:

* This folder (`original_names/`) — basenames you'll recognize, with the
  path lookup in this README.
* Parent folder — long but self-describing filenames; great if you
  want to script the deploy with `cp` or `rsync`.
