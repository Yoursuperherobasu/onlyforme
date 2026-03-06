# Langfuse RBAC Observability Change Log

## Scope
This document captures the complete implementation done for RBAC in Observability with automatic Langfuse provisioning via direct Langfuse DB writes.

Total files changed in current working tree: `19`.

## Final architecture implemented
1. Mapping model:
   - App `Organization -> Langfuse Organization`
   - App `Department -> Langfuse Project`
2. Provisioning model:
   - Automatic provisioning from Agentcore backend by direct writes to Langfuse DB tables.
3. Credential storage:
   - Encrypted at rest in Agentcore `langfuse_binding` table.
4. Read-path RBAC:
   - Scope resolved by role and org/dept memberships.
   - Reads fan out to one or more scoped Langfuse bindings.
5. Write-path routing:
   - Tracing credentials resolved per run from scoped bindings.
   - No legacy global-project fallback when binding is absent.

## Change set summary by layer
1. Database schema:
   - Added `langfuse_binding`, `observability_provision_job`, `observability_schema_lock`.
2. Backend services:
   - Added provisioning engine for Langfuse org/project/api-key creation and reconciliation.
   - Added RBAC scope engine for observability reads/writes.
3. Backend APIs:
   - Added provisioning admin endpoints.
   - Refactored observability APIs to be role scoped and scope-parameter aware.
4. User/org/dept creation flow:
   - Integrated automatic provisioning into root/super-admin flows.
5. Tracing:
   - Added runtime per-binding Langfuse credentials to tracer initialization.
6. Frontend:
   - Added scope selector/filter-first behavior.
   - Added admin provisioning/reconcile panel in Observability page.

## File-by-file documentation (all 19 files)

### 1) `src/backend/base/agentcore/api/__init__.py` (modified)
1. Imported `observability_provisioning_router`.
2. Exported `observability_provisioning_router` in `__all__`.
3. Purpose:
   - Makes new provisioning API module part of backend API package exports.

### 2) `src/backend/base/agentcore/api/router.py` (modified)
1. Imported `observability_provisioning_router`.
2. Included router under `/api`.
3. Purpose:
   - Activates provisioning endpoints in runtime API routing.

### 3) `src/backend/base/agentcore/api/observability.py` (modified, major)
1. Enforced page permission guard:
   - Router now depends on `PermissionChecker(["view_observability_page"])`.
2. Added role-scope resolver integration:
   - Uses `resolve_observability_scope(...)`.
   - Builds scoped Langfuse clients per binding.
3. Added scope warning metadata in responses:
   - `scope_warning`, `scope_warning_message` across traces/sessions/metrics/agents/projects models.
4. Added admin scope query parameters:
   - `org_id`, `dept_id` supported on read endpoints for root/super-admin filter-first behavior.
5. Read fan-out implementation:
   - Fetches data from multiple scoped bindings.
   - De-duplicates by trace id.
6. RBAC filtering:
   - Uses resolved `allowed_user_ids` instead of current-user-only logic.
7. Status endpoint refactor:
   - `/observability/status` now checks scoped binding connectivity for current user context.
8. Trace detail hardening:
   - Cache fallback now accepts traces only when extracted user ids intersect allowed user ids.
   - Rejects traces with missing user ids in security check (`404`).
9. Session/agent/project metrics paths:
   - Refactored to scoped client usage and scope-key cache isolation.
10. Purpose:
   - Converts entire observability read stack from single global Langfuse to RBAC-scoped multi-binding behavior.

### 4) `src/backend/base/agentcore/api/users.py` (modified)
1. Root user flow:
   - After creating organization, triggers `provision_org_admin_project(...)`.
   - Provisioning errors fail request and rollback app transaction.
2. Super admin flow:
   - When creating department admin and new department, triggers `provision_department_project(...)`.
   - Provisioning errors fail and rollback.
3. Purpose:
   - Auto-provision Langfuse resources at org/dept creation points in app workflow.

### 5) `src/backend/base/agentcore/services/database/models/__init__.py` (modified)
1. Added imports/exports:
   - `LangfuseBinding`
   - `ObservabilityProvisionJob`
   - `ObservabilitySchemaLock`
2. Purpose:
   - Registers new models into model discovery/metadata flow.

### 6) `src/backend/base/agentcore/services/tracing/langfuse.py` (modified)
1. `LangFuseTracer` constructor now accepts:
   - `langfuse_host`
   - `langfuse_public_key`
   - `langfuse_secret_key`
2. Client setup updated to prefer explicit runtime credentials over process-global env.
3. Callback handler creation updated:
   - Attempts explicit credential injection when supported.
   - Skips callback when unsupported and explicit credentials are required to avoid cross-tenant leakage.
4. Purpose:
   - Enables safe per-tenant/per-binding trace writes.

### 7) `src/backend/base/agentcore/services/tracing/service.py` (modified)
1. `TraceContext` extended with resolved binding credentials and status flag.
2. Added `_resolve_langfuse_credentials(...)`:
   - Resolves write binding from DB using user/agent scope.
   - Decrypts keys via provisioning service.
3. `start_tracers(...)` now resolves scoped credentials before tracer init.
4. `_initialize_langfuse_tracer(...)` now skips initialization when scoped credentials are not resolved.
5. Purpose:
   - Implements no-legacy-fallback tracing behavior and per-run credential routing.

### 8) `src/frontend/src/pages/ObservabilityPage/index.tsx` (modified, major)
1. Added scope-aware types and API parameter handling:
   - `org_id`, `dept_id` propagated on all observability data calls.
2. Added `scope-options` fetch and role detection.
3. Implemented filter-first gating:
   - For root/super-admin, UI blocks data tabs until org/dept selected.
4. Added scope warning banners from backend response metadata.
5. Added admin provisioning UI (root/super-admin):
   - Provision org admin project
   - Provision department project
   - Reconcile bindings
   - Get job status
   - Retry job
   - Active binding config table (masked keys)
6. Purpose:
   - Completes frontend RBAC observability behavior and provisioning administration.

### 9) `src/backend/base/agentcore/alembic/versions/lf1a2b3c4d5e_add_langfuse_observability_binding_tables.py` (new)
1. Adds `langfuse_binding` table + indexes + partial unique constraints.
2. Adds `observability_provision_job` table + idempotency unique key + indexes.
3. Adds `observability_schema_lock` table + unique version tag.
4. Includes idempotent existence checks and downgrade steps.
5. Purpose:
   - Introduces persistent storage for binding, job tracking, and schema lock safety.

### 10) `src/backend/base/agentcore/api/observability_provisioning.py` (new)
Endpoints added:
1. `POST /observability/provision/org/{org_id}`
2. `POST /observability/provision/dept/{dept_id}`
3. `POST /observability/provision/retry/{job_id}`
4. `GET /observability/provision/status/{job_id}`
5. `GET /observability/config`
6. `POST /observability/provision/reconcile`
7. `GET /observability/scope-options`

Behavior:
1. Restricts provisioning management to `root` and `super_admin`.
2. Enforces org/job scope access checks.
3. Masks key material in config responses.
4. Supports reconciliation response with `healthy/drift/error` summary.

### 11) `src/backend/base/agentcore/services/database/models/langfuse_binding/__init__.py` (new)
1. Exports `LangfuseBinding`.
2. Purpose:
   - Package exposure for new model.

### 12) `src/backend/base/agentcore/services/database/models/langfuse_binding/model.py` (new)
1. Defines binding schema:
   - org/dept scope, langfuse org/project identifiers, host, encrypted keys, audit columns.
2. Defines partial unique constraints:
   - One active org-admin binding per org.
   - One active department binding per dept.
3. Purpose:
   - Core credential and mapping table for multi-tenant observability.

### 13) `src/backend/base/agentcore/services/database/models/observability_provision_job/__init__.py` (new)
1. Exports `ObservabilityProvisionJob`.
2. Purpose:
   - Package exposure for job model.

### 14) `src/backend/base/agentcore/services/database/models/observability_provision_job/model.py` (new)
1. Job tracking fields:
   - idempotency key, scope type, org/dept refs, status, payload hash, retries, error, timestamps.
2. Purpose:
   - Reliable idempotent provisioning tracking and retry support.

### 15) `src/backend/base/agentcore/services/database/models/observability_schema_lock/__init__.py` (new)
1. Exports `ObservabilitySchemaLock`.
2. Purpose:
   - Package exposure for schema lock model.

### 16) `src/backend/base/agentcore/services/database/models/observability_schema_lock/model.py` (new)
1. Stores:
   - `version_tag`, `schema_fingerprint`, `validated_at`.
2. Purpose:
   - Runtime guardrail for pinned Langfuse schema compatibility.

### 17) `src/backend/base/agentcore/services/observability/__init__.py` (new)
1. Exports:
   - Provisioning service and errors.
   - RBAC resolver service and scope error.
2. Purpose:
   - Unified service entry point for observability module.

### 18) `src/backend/base/agentcore/services/observability/provisioning.py` (new, major)
1. Direct Langfuse DB provisioning service:
   - Creates/reuses organizations/projects/memberships/api keys.
2. Safety controls:
   - `OBS_PROVISIONING_ENABLED` gate.
   - Schema fingerprint validation (`LANGFUSE_SCHEMA_LOCK`).
   - Bootstrap user existence check (`LANGFUSE_BOOTSTRAP_USER_EMAIL`).
3. Key handling:
   - Generates public/secret keys.
   - Computes `hashed_secret_key` and `fast_hashed_secret_key`.
   - Verifies credentials via Langfuse client auth check.
4. Persistence in Agentcore:
   - Saves encrypted keys and binding metadata.
   - Updates schema-lock table.
5. Operational resilience:
   - Idempotent job tracking.
   - Cleanup on post-provision verification failure.
6. Drift detection:
   - `reconcile_bindings(...)` compares Agentcore binding data against Langfuse DB rows.
7. Purpose:
   - Implements fully automated provisioning and operational maintenance path.

### 19) `src/backend/base/agentcore/services/observability/rbac.py` (new, major)
1. Role visibility constants:
   - Dept admin visible roles, super-admin visible roles, root visible roles.
2. `resolve_observability_scope(...)`:
   - Resolves allowed org/dept scope and visible user set by role.
   - Enforces filter-first rules for root/super-admin.
   - Loads active bindings for target scope.
3. `resolve_write_langfuse_binding(...)`:
   - Routes write binding by precedence:
     - `agent.dept_id`
     - selected dept
     - first dept membership
     - org-admin binding for root/super-admin
4. Purpose:
   - Central RBAC policy engine for observability reads and writes.

## API changes implemented

### New endpoints
1. `POST /api/observability/provision/org/{org_id}`
2. `POST /api/observability/provision/dept/{dept_id}`
3. `POST /api/observability/provision/retry/{job_id}`
4. `GET /api/observability/provision/status/{job_id}`
5. `POST /api/observability/provision/reconcile`
6. `GET /api/observability/config`
7. `GET /api/observability/scope-options`

### Existing endpoints extended
1. Observability read endpoints now support scoped access (`org_id`, `dept_id`) where applicable.
2. Read responses now include optional warning metadata:
   - `scope_warning`
   - `scope_warning_message`
3. `/api/observability/status` now reports scoped binding connectivity.

## Configuration and env dependencies introduced
1. `OBS_PROVISIONING_ENABLED`
2. `LANGFUSE_DB_URL`
3. `LANGFUSE_HOST` or `LANGFUSE_BASE_URL`
4. `LANGFUSE_BOOTSTRAP_USER_EMAIL`
5. `LANGFUSE_SCHEMA_LOCK`
6. `LANGFUSE_SCHEMA_VERSION_TAG`
7. `LANGFUSE_HASH_STRATEGY_VERSION`
8. `LANGFUSE_SALT`
9. `OBSERVABILITY_ENCRYPTION_KEY`

## Behavior matrix implemented
1. `business_user` / `developer`:
   - Read own traces only.
   - Write to department-scoped project.
2. `department_admin`:
   - Read own + dept business/developer.
3. `super_admin`:
   - Read scoped-org users (`department_admin`, `business_user`, `developer`), filter-first.
4. `root`:
   - Read global by selected org/dept scope, filter-first.
5. `super_admin` / `root` writes:
   - Route to org-admin project when dept route not selected.

## Security and integrity changes
1. Encrypted key storage in Agentcore DB only.
2. Scoped client initialization from bindings, not global env.
3. Tracing disabled when scoped binding is missing or unresolved.
4. Trace-detail security tightened:
   - Disallows unresolved/no-user-id traces from scoped cache fallback.
5. Provisioning idempotency and retry tracking added.
6. Reconciliation endpoint added for drift detection.

## Validation status at implementation time
1. Backend compile checks for touched Python files passed.
2. Observability page targeted TypeScript check had no file-specific errors.
3. Full frontend type-check still reports unrelated pre-existing errors outside observability scope.

## Notes
1. This implementation is currently in working tree and not yet committed.
2. File count `19` corresponds to expanded `git status --short --untracked-files=all`.
