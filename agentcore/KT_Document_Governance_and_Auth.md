# AgentCore - Knowledge Transfer Document

---

# SESSION 1: Governance (RBAC, Multi-Tenancy, Approval Workflows)

---

## 1. RBAC (Role-Based Access Control)

### 1.1 Architecture Overview

```
                    +-----------+
                    |   User    |
                    +-----+-----+
                          |
                   +------+------+
                   |    Role     |  (role table)
                   +------+------+
                          |
                +--------+--------+
                | RolePermission  |  (role_permission table)
                +--------+--------+
                          |
                   +------+------+
                   | Permission  |  (permission table)
                   +-------------+
                          |
                   +------+------+
                   | Redis Cache |  (TTL-based)
                   +-------------+
```

### 1.2 Role Hierarchy — 7 Roles

**File:** `src/backend/base/agentcore/services/auth/permissions.py`

| Role | Scope | Key Permissions |
|------|-------|-----------------|
| `root` (Line 148) | System-wide | ALL permissions |
| `super_admin` (Line 201) | Organization-level | Nearly all (excludes `publish_release`, `view_access_control_page`) |
| `department_admin` (Line 250) | Department-level | Same as super_admin |
| `developer` (Line 299) | Create/Request | view/request/interact (no delete/retire, no admin) |
| `business_user` (Line 330) | Interact/Request | Same as developer |
| `consumer` (Line 361) | Minimal | `view_published_agents`, `interact_agents` only |
| `leader_executive` (Line 198) | Dashboard only | `view_dashboard` only |

**Code — ROLE_PERMISSIONS dictionary (Lines 147-367):**

```python
# permissions.py — Line 147
ROLE_PERMISSIONS: dict[str, list[str]] = {

    # ── ROOT (Line 148-197) ──────────────────────────────────────
    "root": [
        "view_dashboard",
        "view_admin_page",
        "view_approval_page",
        "view_agents_page",
        "view_projects_page",
        "edit_agents",
        "publish_release",
        "move_uat_to_prod",
        "hitl_approve",
        "hitl_reject",
        "add_guardrails",
        "retire_guardrails",
        "delete_vector_db_catalogue",
        "edit_mcp",
        "view_access_control_page",
        "view_connector_page",
        # ... (full list ~50 permissions)
    ],

    # ── LEADER_EXECUTIVE (Line 198-200) ──────────────────────────
    "leader_executive": [
        "view_dashboard",
    ],

    # ── CONSUMER (Line 361-366) ──────────────────────────────────
    "consumer": [
        "view_published_agents",
        "view_registry_agent",
        "view_orchastration_page",
        "interact_agents",
    ],
}
```

### 1.3 Permission Checker Decorator

**File:** `src/backend/base/agentcore/services/auth/decorators.py`

```python
# decorators.py — Lines 9-54
class PermissionChecker:
    def __init__(self, required_permissions: list[str], all_required: bool = True):
        self.required_permissions = required_permissions
        self.all_required = all_required

    async def __call__(self, current_user=Depends(get_current_active_user)):
        user_permissions = await get_permissions_for_role(current_user.role)

        if self.all_required:
            # User must have ALL listed permissions
            missing = set(self.required_permissions) - set(user_permissions)
            if missing:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
        else:
            # User needs at least ONE permission
            if not set(self.required_permissions) & set(user_permissions):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

        return current_user
```

**Usage in API endpoints:**

```python
# Example from roles.py — Line 41
@router.get("/permissions")
async def list_permissions(
    current_user=Depends(PermissionChecker(["view_access_control_page"])),
):
    ...
```

### 1.4 Redis Permission Cache

**File:** `src/backend/base/agentcore/services/auth/permissions.py`

```python
# permissions.py — Lines 369-447

PERMISSION_VERSION = "v22"   # Line 369 — bump this to invalidate all caches

class PermissionCacheService:
    def __init__(self, settings_service: SettingsService):           # Line 373
        self.settings_service = settings_service
        self.redis = get_redis_client(settings_service)
        self.ttl = settings_service.settings.redis_cache_expire

    async def get_permissions_for_role(self, role: str) -> list[str]:  # Line 396
        cache_key = f"role:{PERMISSION_VERSION}:{role}"

        # Root users ALWAYS query DB (bypass cache)                    # Line 396-404
        if _normalize_role(role) == "root":
            db_perms = await _get_permissions_for_role_db(role)
            merged = list(set(ROLE_PERMISSIONS.get("root", []) + db_perms))
            return merged

        # Try Redis cache first
        cached = await self._redis_call_with_reconnect(
            self.redis.get, cache_key
        )
        if cached:
            return json.loads(cached)

        # Cache miss → query DB → store in Redis with TTL
        db_perms = await _get_permissions_for_role_db(role)
        if db_perms:
            await self._redis_call_with_reconnect(
                self.redis.setex, cache_key, self.ttl, json.dumps(db_perms)
            )
        return db_perms
```

**Cache Invalidation:**

```python
# permissions.py — Lines 513-521
async def invalidate_role_permissions_cache(role: str):
    cache_key = f"role:{PERMISSION_VERSION}:{role}"
    redis = get_redis_client(settings_service)
    await redis.delete(cache_key)
```

### 1.5 Permission Aliases (Backward Compatibility)

**File:** `src/backend/base/agentcore/services/auth/permissions.py` — Lines 20-71

```python
# permissions.py — Lines 20-71
PERMISSION_ALIASES: dict[str, list[str]] = {
    "view_project_page":  ["view_projects_page"],
    "manage_users":       ["view_admin_page"],
    "manage_roles":       ["view_access_control_page"],
    # ... maps old permission names → new names
}
```

### 1.6 Role Management API

**File:** `src/backend/base/agentcore/api/roles.py`

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/permissions` | GET | 41 | List all permissions |
| `/roles` | GET | 55 | List all roles with their permissions |
| `/roles` | POST | 84 | Create new custom role |
| `/roles/{role_id}` | PATCH | 135 | Update role (prevents renaming system roles) |
| `/roles/{role_id}/permissions` | PUT | 186 | Replace all permissions for a role |

---

## 2. Multi-Tenancy

### 2.1 Tenant Hierarchy

```
  Organization (Org)
       |
       +--- tier: free | standard | enterprise
       +--- status: active | suspended | deleted
       +--- owner_user_id
       |
       +--- Department (Dept)
                |
                +--- org_id (FK → Organization)
                +--- admin_user_id
                +--- status: active | archived
                |
                +--- Users (via membership tables)
                        |
                        +--- UserOrganizationMembership
                        +--- UserDepartmentMembership
```

### 2.2 Organization Model

**File:** `src/backend/base/agentcore/services/database/models/organization/model.py`

```python
# organization/model.py — Lines 9-63

class OrgTierEnum(str, Enum):          # Line 9
    FREE = "free"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"

class OrgStatusEnum(str, Enum):        # Line 15
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class Organization(SQLModel, table=True):  # Line 21
    id: UUID = Field(default_factory=uuid4, primary_key=True)              # Line 22
    name: str = Field(sa_column=Column(String(255), nullable=False))       # Line 23
    description: str | None = Field(default=None)                          # Line 24
    tier: OrgTierEnum = Field(default=OrgTierEnum.STANDARD)                # Line 25
    status: OrgStatusEnum = Field(default=OrgStatusEnum.ACTIVE)            # Line 37
    owner_user_id: UUID = Field(foreign_key="user.id", nullable=False)     # Line 49
    created_by: UUID = Field(foreign_key="user.id", nullable=False)        # Line 50
    created_at: datetime                                                    # Line 51
    updated_by: UUID | None                                                 # Line 55
    updated_at: datetime                                                    # Line 56

    __table_args__ = (
        Index("ix_organization_name", "name", unique=True),                # Line 62
    )
```

### 2.3 Department Model

**File:** `src/backend/base/agentcore/services/database/models/department/model.py`

```python
# department/model.py — Lines 9-48

class DeptStatusEnum(str, Enum):       # Line 9
    ACTIVE = "active"
    ARCHIVED = "archived"

class Department(SQLModel, table=True):  # Line 14
    id: UUID = Field(default_factory=uuid4, primary_key=True)              # Line 15
    org_id: UUID = Field(foreign_key="organization.id", nullable=False)    # Line 16
    name: str = Field(sa_column=Column(String(255), nullable=False))       # Line 17
    description: str | None                                                 # Line 18
    code: str | None = Field(sa_column=Column(String(50)))                 # Line 19
    parent_dept_id: UUID | None = Field(foreign_key="department.id")       # Line 20
    admin_user_id: UUID = Field(foreign_key="user.id", nullable=False)     # Line 21
    status: DeptStatusEnum = Field(default=DeptStatusEnum.ACTIVE)          # Line 22

    __table_args__ = (
        UniqueConstraint("org_id", "id", name="uq_department_org_id_id"),       # Line 46
        UniqueConstraint("org_id", "name", name="uq_department_org_name"),      # Line 47
    )
```

### 2.4 User-Organization Membership

**File:** `src/backend/base/agentcore/services/database/models/user_organization_membership/model.py`

```python
# user_organization_membership/model.py — Lines 8-32

class UserOrganizationMembership(SQLModel, table=True):  # Line 8
    __tablename__ = "user_organization_membership"

    id: UUID = Field(default_factory=uuid4, primary_key=True)          # Line 11
    user_id: UUID = Field(foreign_key="user.id", nullable=False)       # Line 12
    org_id: UUID = Field(foreign_key="organization.id", nullable=False)# Line 13
    status: str = Field(default="invited")  # invited | accepted | active  # Line 14
    role_id: UUID = Field(foreign_key="role.id", nullable=False)       # Line 15
    invited_by: UUID | None = Field(foreign_key="user.id")             # Line 16
    accepted_at: datetime | None                                        # Line 17
    created_at: datetime                                                # Line 18
    updated_at: datetime                                                # Line 22

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_uom_user_org"),    # Line 28
    )
```

### 2.5 User-Department Membership

**File:** `src/backend/base/agentcore/services/database/models/user_department_membership/model.py`

```python
# user_department_membership/model.py — Lines 8-38

class UserDepartmentMembership(SQLModel, table=True):  # Line 8
    __tablename__ = "user_department_membership"

    id: UUID = Field(default_factory=uuid4, primary_key=True)              # Line 11
    user_id: UUID = Field(foreign_key="user.id", nullable=False)           # Line 12
    org_id: UUID = Field(foreign_key="organization.id", nullable=False)    # Line 13
    department_id: UUID = Field(foreign_key="department.id", nullable=False) # Line 14
    status: str = Field(default="active")                                   # Line 15
    role_id: UUID = Field(foreign_key="role.id", nullable=False)           # Line 16
    assigned_by: UUID | None = Field(foreign_key="user.id")                # Line 17

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", "department_id",
                         name="uq_udm_user_org_department"),               # Line 29
        ForeignKeyConstraint(
            ["org_id", "department_id"],
            ["department.org_id", "department.id"],
            name="fk_udm_org_department",                                  # Line 30-33
        ),
    )
```

### 2.6 Tenant Scoping — How Entities are Isolated

**File:** `src/backend/base/agentcore/components/models/_rbac_helpers.py`

Every entity (Agent, Model, MCP, Guardrail) has:
```python
org_id: UUID | None = Field(foreign_key="organization.id", nullable=True)
dept_id: UUID | None = Field(foreign_key="department.id", nullable=True)
```

**Membership Resolution (Lines 91-141):**

```python
# _rbac_helpers.py — Lines 91-141
async def get_user_memberships_async(user_id: UUID):
    """Returns (role, username, org_ids, dept_ids) for a user."""

    # Query UserOrganizationMembership
    # Filter: status IN ("accepted", "active")
    org_ids = [row.org_id for row in org_memberships]

    # Query UserDepartmentMembership
    # Filter: status == "active"
    dept_ids = [row.department_id for row in dept_memberships]

    return (role, username, org_ids, dept_ids)
```

**Visibility Check — can_access_model_dict() (Lines 200-256):**

```python
# _rbac_helpers.py — Lines 200-256
def can_access_model_dict(model: dict, role, org_ids, dept_ids, user_id):
    # Root → always True
    if normalize_role(role) == "root":
        return True

    # Super Admin → check org_id membership
    if normalize_role(role) == "super_admin":
        return model["org_id"] in org_ids

    # Department Admin → check dept membership OR public_dept_ids overlap
    if normalize_role(role) == "department_admin":
        if model["dept_id"] in dept_ids:
            return True
        if set(model.get("public_dept_ids", [])) & set(dept_ids):
            return True
        return False

    # Visibility scopes:
    #   PRIVATE     → only creator or requester can see
    #   DEPARTMENT  → department members can see
    #   ORGANIZATION → organization members can see
```

**Query Filtering in agent.py (Lines 145-170):**

```python
# api/agent.py — Lines 145-170
if normalize_role(current_user.role) == "super_admin":
    org_ids = await _get_scope_memberships(session, current_user.id)
    # WHERE agent.org_id IN (org_ids)

elif normalize_role(current_user.role) == "department_admin":
    dept_ids = await _get_scope_memberships(session, current_user.id)
    # WHERE agent.dept_id IN (dept_ids)
```

### 2.7 Multi-Tenancy — Database Schema Diagram

```
┌──────────────────────┐     ┌───────────────────────────────┐
│   organization       │     │  user_organization_membership │
│──────────────────────│     │───────────────────────────────│
│ id (PK)              │◄────│ org_id (FK)                   │
│ name (UNIQUE)        │     │ user_id (FK → user)           │
│ tier (enum)          │     │ role_id (FK → role)           │
│ status (enum)        │     │ status (invited/accepted/active)│
│ owner_user_id (FK)   │     │ UNIQUE(user_id, org_id)       │
└──────────────────────┘     └───────────────────────────────┘
          │
          │ 1:N
          ▼
┌──────────────────────┐     ┌───────────────────────────────┐
│   department         │     │  user_department_membership   │
│──────────────────────│     │───────────────────────────────│
│ id (PK)              │◄────│ department_id (FK)            │
│ org_id (FK → org)    │     │ org_id (FK → org)             │
│ name                 │     │ user_id (FK → user)           │
│ admin_user_id (FK)   │     │ role_id (FK → role)           │
│ status (enum)        │     │ UNIQUE(user_id, org_id, dept) │
│ UNIQUE(org_id, name) │     │ FK(org_id,dept_id) → dept     │
└──────────────────────┘     └───────────────────────────────┘
```

---

## 3. Approval Workflows

### 3.1 Three Approval Types

| Type | Model | File | Purpose |
|------|-------|------|---------|
| Agent | `ApprovalRequest` | `approval_request/model.py` | Publish agent to PROD |
| Model | `ModelApprovalRequest` | `model_approval_request/model.py` | Promote model UAT→PROD, change visibility |
| MCP | `McpApprovalRequest` | `mcp_approval_request/model.py` | Change MCP server visibility/scope |

### 3.2 Approval Decision Enum

**File:** `src/backend/base/agentcore/services/database/models/approval_request/model.py` — Lines 20-25

```python
class ApprovalDecisionEnum(str, Enum):
    APPROVED  = "APPROVED"
    REJECTED  = "REJECTED"
    CANCELLED = "CANCELLED"
```

### 3.3 Agent Approval Request Model

**File:** `src/backend/base/agentcore/services/database/models/approval_request/model.py` — Lines 28-138

```python
# approval_request/model.py — Lines 28-138

class ApprovalRequestBase(SQLModel):
    agent_id: UUID = Field(foreign_key="agent.id")                     # Line 33
    deployment_id: UUID = Field(foreign_key="agent_deployment_prod.id") # Line 36
    org_id: UUID | None = Field(foreign_key="organization.id")         # tenant scope
    dept_id: UUID | None = Field(foreign_key="department.id")          # tenant scope
    requested_by: UUID = Field(foreign_key="user.id")                  # Line 44 — who requested
    request_to: UUID = Field(foreign_key="user.id")                    # Line 49 — approver
    reviewed_by: UUID | None = Field(foreign_key="user.id")            # Line 54 — who reviewed
    decision: ApprovalDecisionEnum | None                              # Line 65
    justification: str | None                                          # Line 76 — reviewer comments
    visibility_requested: ProdDeploymentVisibilityEnum                 # Line 81
    publish_description: str | None                                    # Line 94
    file_path: dict | None                                             # Line 99 — attachments
    requested_at: datetime                                             # timestamp
    reviewed_at: datetime | None                                       # timestamp

class ApprovalRequest(ApprovalRequestBase, table=True):                # Line 114
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Indexes: deployment_id, org_id, dept_id,
    #          (request_to + decision), (requested_by + decision)
```

### 3.4 Model Approval Request

**File:** `src/backend/base/agentcore/services/database/models/model_approval_request/model.py` — Lines 13-74

```python
# model_approval_request/model.py

class ModelApprovalRequestType(str, Enum):    # Line 13
    CREATE    = "create"       # New model registration
    PROMOTE   = "promote"      # UAT → PROD promotion
    VISIBILITY = "visibility"  # Change visibility scope

class ModelApprovalRequestBase(SQLModel):     # Line 19
    model_id: UUID = Field(foreign_key="model_registry.id")            # Line 20
    request_type: ModelApprovalRequestType                              # Line 23
    source_environment: str   # default "UAT"                          # Line 27
    target_environment: str   # target (e.g., "PROD")                  # Line 31
    requested_environments: list[str]                                   # Line 35
    visibility_requested: ModelVisibilityScope                          # Line 37
    #   ModelVisibilityScope: PRIVATE | DEPARTMENT | ORGANIZATION
    public_dept_ids: list[str]  # departments with access              # Line 41
    requested_by: UUID                                                  # Line 42
    request_to: UUID                                                    # Line 43
    reviewed_by: UUID | None                                            # Line 44
    decision: ApprovalDecisionEnum | None                               # Line 50
    justification: str | None                                           # Line 51
```

### 3.5 MCP Approval Request

**File:** `src/backend/base/agentcore/services/database/models/mcp_approval_request/model.py` — Lines 12-59

```python
# mcp_approval_request/model.py

class McpApprovalRequestBase(SQLModel):       # Line 12
    mcp_id: UUID = Field(foreign_key="mcp_registry.id")                # Line 13
    deployment_env: str            # "UAT" or "PROD"                   # Line 27
    requested_environments: list[str]                                   # Line 32
    requested_visibility: str      # visibility setting                # Line 33
    requested_public_scope: str    # "organization" or "department"    # Line 34
    requested_org_id: UUID | None                                       # Line 35
    requested_dept_id: UUID | None                                      # Line 36
    requested_public_dept_ids: list[str]                                # Line 37
    requested_by: UUID                                                  # Line 16
    request_to: UUID                                                    # Line 17
    reviewed_by: UUID | None                                            # Line 18
    decision: ApprovalDecisionEnum | None                               # Line 24
    justification: str | None                                           # Line 25
    file_path: dict | None         # attachments                       # Line 26
```

### 3.6 Approval Workflow — Complete Flow

**File:** `src/backend/base/agentcore/api/approvals.py`

```
  Developer                    System                      Approver (dept_admin/root)
     |                           |                                |
     |  Request Publish/Promote  |                                |
     |-------------------------->|                                |
     |                           |  Create ApprovalRequest        |
     |                           |  (decision=None, PENDING)      |
     |                           |                                |
     |                           |  upsert_approval_notification  |
     |                           |------------------------------->|
     |                           |  notify_root_approvers()       |
     |                           |------------------------------->|
     |                           |                                |
     |                           |     GET /approvals             |
     |                           |<-------------------------------|
     |                           |     (view pending requests)    |
     |                           |                                |
     |                           |   POST /approvals/{agent_id}   |
     |                           |<-------------------------------|
     |                           |   (comments + attachments)     |
     |                           |                                |
     |                           |  If APPROVED:                  |
     |                           |    - Mark deployment APPROVED  |
     |                           |    - Promote guardrails        |
     |                           |    - Migrate Pinecone vectors  |
     |                           |    - Sync to prod registry     |
     |                           |                                |
     |                           |  If REJECTED:                  |
     |                           |    - Mark deployment REJECTED  |
     |                           |    - Notify requester          |
     |  Notification received    |                                |
     |<--------------------------|                                |
```

### 3.7 Approval Access Control

**File:** `src/backend/base/agentcore/api/approvals.py` — Lines 761-845

```python
# approvals.py — Lines 761-797
async def _get_approval_for_action(approval_or_agent_id, current_user):
    """Who can APPROVE/REJECT a request?"""

    # Find the approval request (by approval_id or agent_id)
    req = await _find_approval_request(approval_or_agent_id, session)

    # Check: is current user the designated approver?
    if req.request_to == current_user.id:                              # Line 790
        return req

    # Check: is current user a super_admin for the same org?
    if current_user.role == "super_admin":                             # Line 791
        org_ids = await _designated_super_admin_org_ids(current_user)
        if req.org_id in org_ids:
            return req

    # Otherwise → 403 Forbidden
    raise HTTPException(status_code=403)
```

```python
# approvals.py — Lines 800-845
async def _get_approval_for_view(approval_or_agent_id, current_user):
    """Who can VIEW a request?"""
    req = await _find_approval_request(...)

    # Requester can view their own request
    if req.requested_by == current_user.id:                            # Line 824
        return req
    # Approver can view
    if req.request_to == current_user.id:                              # Line 825
        return req
    # Super admin for same org can view
    if current_user.role in ("super_admin", "root"):                   # Line 826-827
        return req

    raise HTTPException(status_code=403)
```

### 3.8 approve_agent() — Main Approval Handler

**File:** `src/backend/base/agentcore/api/approvals.py` — Lines 1396-1599

```python
# approvals.py — Lines 1396-1599
async def approve_agent(
    agent_id: str,
    session: DbSession,
    current_user: CurrentActiveUser,
    comments: str = Form(default=""),
    attachments: list[UploadFile] | None = File(default=None),
) -> ApprovalResponse:

    # Step 1: Try to find as Agent approval, then MCP, then Model (Lines 1414-1436)
    # Three-tier fallback pattern

    # ── MCP Approval (Lines 1438-1514) ──────────────────────────
    if mcp_approval:
        mcp_approval.decision = ApprovalDecisionEnum.APPROVED          # Line 1450
        mcp_approval.reviewed_by = current_user.id                     # Line 1451
        mcp_approval.justification = comments                          # Line 1452

        # Update McpRegistry visibility (Lines 1471-1478)
        mcp_row.visibility = mcp_approval.requested_visibility
        mcp_row.public_scope = mcp_approval.requested_public_scope

        # Sync to MCP service (Lines 1480-1491)
        await update_mcp_server_via_service(mcp_row)

        # Notify requester (Lines 1495-1502)
        await upsert_approval_notification(session, ...)

    # ── Model Approval (Lines 1516-1599) ────────────────────────
    if model_approval:
        model_approval.decision = ApprovalDecisionEnum.APPROVED        # Line 1528
        model_approval.reviewed_by = current_user.id                   # Line 1529

        if model_approval.request_type == "promote":                   # Line 1548
            # Validate: only UAT → PROD allowed
            model_row.environments.append(target_env)
            model_row.approval_status = "APPROVED"

        elif model_approval.request_type == "visibility":              # Line 1575
            # Update visibility_scope (PRIVATE/DEPARTMENT/ORGANIZATION)
            model_row.visibility_scope = model_approval.visibility_requested
            model_row.public_dept_ids = model_approval.public_dept_ids
```

### 3.9 Post-Approval: Guardrail Promotion

**File:** `src/backend/base/agentcore/api/approvals.py` — Lines 228-279

```python
# approvals.py — Lines 228-279
async def _promote_guardrails_for_deployment(
    snapshot: dict,
    promoted_by: UUID,
) -> list[GuardrailPromotionResult]:
    """Extracts NemoGuardrails nodes from agent snapshot, promotes each to PROD."""

    # Extract guardrail nodes from snapshot (Lines 239-242)
    nemo_nodes = [n for n in snapshot.get("nodes", [])
                  if n.get("type") == "NemoGuardrails"]

    results = []
    for node in nemo_nodes:
        # Call guardrail service to promote (Lines 260-263)
        result = await promote_guardrail_via_service(
            guardrail_id=node["guardrail_id"],
            promoted_by=promoted_by,
        )
        results.append(result)

    return results
```

### 3.10 Post-Approval: Pinecone Vector Migration

**File:** `src/backend/base/agentcore/api/approvals.py` — Lines 298-399

```python
# approvals.py — Lines 298-399
async def _migrate_pinecone_for_prod(
    deployment: AgentDeploymentProd,
    session: DbSession,
) -> None:
    """Copy vector namespaces from UAT to PROD."""

    # Phase 1: Collect Pinecone nodes needing migration (Lines 328-361)
    for node in pinecone_nodes:
        prod_namespace = f"{original_namespace}_prod_v{version}"

    # Phase 2: Execute copies atomically (Lines 363-399)
    for ns in namespaces_to_copy:
        await copy_pinecone_namespace(source=ns.uat, target=ns.prod)
        # Update snapshot with new PROD namespace
```

### 3.11 Approval Notifications

**File:** `src/backend/base/agentcore/services/approval_notifications.py`

```python
# approval_notifications.py — Lines 13-51
async def upsert_approval_notification(
    session,
    *,
    recipient_user_id: UUID,
    entity_type: str,          # "agent_request_result", "mcp_request_result", etc.
    entity_id: str,
    title: str,
    link: str = "/approval",
) -> ApprovalNotification:
    # Check if notification already exists
    existing = await session.exec(
        select(ApprovalNotification)
        .where(ApprovalNotification.recipient_user_id == recipient_user_id)
        .where(ApprovalNotification.entity_type == entity_type)
        .where(ApprovalNotification.entity_id == entity_id)
    )
    if existing:
        existing.is_read = False       # Reset read status
        existing.title = title
    else:
        notification = ApprovalNotification(
            recipient_user_id=recipient_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            link=link,
            is_read=False,
        )
        session.add(notification)
```

```python
# approval_notifications.py — Lines 54-84
async def notify_root_approvers(session, *, entity_type, entity_id, title, link="/approval"):
    """Notify ALL root users about an approval request."""
    root_users = await session.exec(
        select(User)
        .where(User.role == "root")
        .where(User.is_active == True)
        .where(User.deleted_at.is_(None))
    )
    for user in root_users:
        await upsert_approval_notification(session, recipient_user_id=user.id, ...)
```

### 3.12 Integration: RBAC + Multi-Tenancy + Approvals

**Example Flow — Developer publishes agent in Department D1, Org O1:**

```
1. DEVELOPER (role=developer, dept_id=D1, org_id=O1)
   └─ Creates agent → agent.org_id=O1, agent.dept_id=D1
   └─ Requests UAT→PROD publish
   └─ ApprovalRequest created:
        requested_by = developer.id
        request_to   = department_admin.id (D1's admin)
        org_id       = O1
        dept_id      = D1

2. DEPARTMENT_ADMIN (role=department_admin, dept_id=D1)
   └─ Has permission: "hitl_approve" ← checked by PermissionChecker
   └─ Query filter: can only see agents WHERE dept_id IN (their active depts)
   └─ Views approval → _get_approval_for_view() → allowed (is request_to)
   └─ Approves → _get_approval_for_action() → allowed

3. POST-APPROVAL
   └─ AgentDeploymentProd.status = APPROVED
   └─ Guardrails promoted from UAT → PROD
   └─ Pinecone vectors copied: namespace → namespace_prod_v1
   └─ Developer notified via ApprovalNotification

4. TENANT ISOLATION GUARANTEE
   └─ Super admin from Org O2 CANNOT see/approve Org O1's agents
   └─ Dept admin from D2 CANNOT act on D1's approvals
   └─ Enforced at DB level via WHERE clauses on org_id/dept_id
```

---
---

# SESSION 2: Authorization & Platform Pages

---

## 1. Authentication Architecture — 3 Paths

```
┌──────────────────────────────────────────────────────────┐
│                    USER LOGIN                            │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Path 1:     │  │ Path 2:      │  │ Path 3:        │  │
│  │ OKTA/MAS    │  │ Azure        │  │ Dev Fallback   │  │
│  │ JWT Bearer  │  │ EasyAuth     │  │ sample_user    │  │
│  │ (Priority 1)│  │ (Priority 2) │  │ (Priority 3)   │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

| Path | Who | Trigger | Token Type |
|------|-----|---------|------------|
| OKTA/MAS JWT | MAS domain users | `Authorization: Bearer` header | HS256 JWT (8hr) |
| Azure EasyAuth | Motherson web users on Azure | `x-ms-client-principal-*` headers | Azure headers |
| Dev Fallback | Local development | Neither above present | Hardcoded sample |

---

## 2. OKTA/MAS Login Flow (Complete)

### 2.1 MAS Domain Whitelist

**Frontend — File:** `MiBuddy-Backend/frontend/src/ProtectedRoute.tsx` — Line 11

```typescript
// ProtectedRoute.tsx — Line 11
const MAS_WIN_DOMAINS = ["adgroupe", "adi-kalfa", "exameca", "mbsctdom01", "mercure"];
```

**Backend — File:** `MiBuddy-Backend/app.py` — Line 526

```python
# app.py — Line 526
MAS_ALLOWED_EMAIL_DOMAINS: set[str] = {"motherson-mas.com"}
```

### 2.2 Step 1: Initiate OKTA Login

**File:** `MiBuddy-Backend/app.py` — Lines 536-561

```python
# app.py — Lines 536-561
@app.get("/auth/mas/start")
async def mas_auth_start(request: Request):
    """MAS users initiated from ProtectedRoute"""
    state = secrets.token_urlsafe(32)                                  # Line 539 — CSRF token
    redirect_uri = _get_okta_redirect_uri(request)                     # Line 540

    params = {
        "client_id":     OKTA_CLIENT_ID,                               # Line 544
        "response_type": "code",                                       # Line 545
        "scope":         "openid profile email",                       # Line 546
        "redirect_uri":  redirect_uri,                                 # Line 547
        "state":         state,                                        # Line 548
    }
    okta_url = f"{OKTA_ISSUER}/oauth2/v1/authorize?" + urlencode(params)  # Line 550

    response = RedirectResponse(url=okta_url, status_code=302)         # Line 552
    response.set_cookie(
        "okta_state",
        state,
        httponly=True,           # Not accessible via JavaScript         # Line 556
        samesite="lax",
        max_age=600,             # 10 minute TTL                        # Line 558
        secure=is_https,
    )
    return response
```

### 2.3 Step 2: OKTA Callback — Exchange Code for Token

**File:** `MiBuddy-Backend/app.py` — Lines 569-670

```python
# app.py — Lines 569-670
@app.get("/authorization-code/callback")
async def okta_callback(request: Request, code: str, state: str):

    # ── Validate CSRF state (Lines 585-588) ────────────────────
    saved_state = request.cookies.get("okta_state", "")                # Line 585
    if not saved_state or saved_state != state:                        # Line 586
        logger.warning("OKTA state mismatch — possible CSRF")         # Line 587
        raise HTTPException(status_code=400, detail="Invalid state")   # Line 588

    # ── Exchange auth code for OKTA access token (Lines 598-609) ───
    token_resp = requests.post(
        f"{OKTA_ISSUER}/oauth2/v1/token",                              # Line 599
        data={
            "grant_type":    "authorization_code",                     # Line 601
            "code":          code,                                     # Line 602
            "redirect_uri":  redirect_uri,                             # Line 603
            "client_id":     OKTA_CLIENT_ID,                           # Line 604
            "client_secret": OKTA_CLIENT_SECRET,                       # Line 605
        },
        headers={"Accept": "application/json"},                        # Line 607
        timeout=15,                                                    # Line 608
    )
    access_token = token_resp.json().get("access_token", "")           # Line 610

    # ── Fetch user info from OKTA (Lines 622-627) ─────────────────
    ui_resp = requests.get(
        f"{OKTA_ISSUER}/oauth2/v1/userinfo",                           # Line 623
        headers={"Authorization": f"Bearer {access_token}"},           # Line 624
        timeout=10,                                                    # Line 625
    )
    okta_user = ui_resp.json()                                         # Line 627
    email = okta_user.get("email", "").lower()                         # Line 628
    email_domain = email.split("@")[1] if "@" in email else ""         # Line 629

    # ── Validate email domain (Lines 638-643) ─────────────────────
    if email_domain not in MAS_ALLOWED_EMAIL_DOMAINS:                  # Line 638
        raise HTTPException(status_code=403,
            detail=f"Your email domain '{email_domain}' is not allowed")

    # ── Issue signed MiBuddy JWT (Lines 646-658) ──────────────────
    mibuddy_jwt = pyjwt.encode(
        {
            "UserId":        okta_user.get("sub", ""),                 # Line 648
            "email":         email,                                    # Line 649
            "name":          okta_user.get("name", email.split("@")[0]),# Line 650
            "Domain":        email_domain,                             # Line 651
            "auth_provider": "okta",                                   # Line 652
            "iat":           datetime.utcnow(),                        # Line 653
            "exp":           datetime.utcnow() + timedelta(hours=8),   # Line 654
        },
        YOUR_SECRET_KEY,                                               # Line 656
        algorithm="HS256",                                             # Line 657
    )

    # ── Redirect to frontend with JWT in URL (Lines 664-670) ──────
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    app_url = f"{scheme}://{host}/?mas_token={mibuddy_jwt}"            # Line 666

    response = RedirectResponse(url=app_url, status_code=302)          # Line 668
    response.delete_cookie("okta_state")                               # Line 669
    return response
```

### 2.4 JWT Token Structure

```json
{
  "UserId":        "00u1abc2def3ghi4j",     // OKTA sub claim
  "email":         "john.doe@motherson-mas.com",
  "name":          "John Doe",
  "Domain":        "motherson-mas.com",
  "auth_provider": "okta",
  "iat":           1713800000,              // Issued at
  "exp":           1713828800               // Expires in 8 hours
}
// Algorithm: HS256
// Secret: YOUR_SECRET_KEY
```

### 2.5 OKTA Configuration

**File:** `MiBuddy-Backend/backend/utils/environ.py` — Lines 254-256

```python
# environ.py — Lines 254-256
OKTA_ISSUER       = os.environ.get("OKTA_ISSUER",       "https://mothersongroup.okta.com")
OKTA_CLIENT_ID    = os.environ.get("OKTA_CLIENT_ID",    "0oas3fslh2iN9AdRD697")
OKTA_CLIENT_SECRET= os.environ.get("OKTA_CLIENT_SECRET", "K97vOBiA3z...")
```

**JWT Secret Keys — Lines 186-187:**

```python
# environ.py — Lines 186-187
YOUR_SECRET_KEY         = os.environ.get("YOUR_SECRET_KEY",         "56fb22c7...")
YOUR_REFRESH_SECRET_KEY = os.environ.get("YOUR_REFRESH_SECRET_KEY", "149cd3ec...")
```

---

## 3. Standard Motherson Login (Azure EasyAuth)

### 3.1 /login Endpoint

**File:** `MiBuddy-Backend/app.py` — Lines 494-520

```python
# app.py — Lines 494-520
@app.post("/login")
async def login(request: LoginRequest):
    table_service_client = TableServiceClient.from_connection_string(   # Line 496
        conn_str=conn_str
    )
    table_client = table_service_client.get_table_client(               # Line 497
        table_name=TABLE_USER_AUTH       # "tblUserAuthorization"
    )
    user_data = table_client.list_entities()                            # Line 498

    user = next(
        (u for u in user_data
         if u["WindowUserId"].lower() == request.UserName.lower()       # Line 501
         and u["Domain"].lower() == request.Domain.lower()              # Line 502
         and u["Active"] is True),                                      # Line 503
        None,
    )

    # NOTE: Always returns True — Azure EasyAuth on App Service
    # is the real security gate, not this endpoint
    return {"Message": True}                                            # Line 507
```

### 3.2 Azure EasyAuth Headers

When running on Azure App Service, these headers are automatically injected:

| Header | Purpose |
|--------|---------|
| `x-ms-client-principal-id` | Azure AD user object ID |
| `x-ms-client-principal-name` | User display name / email |
| `x-ms-client-principal-idp` | Identity provider (e.g., "aad") |
| `x-ms-token-aad-id-token` | Azure AD ID token |
| `x-ms-client-principal` | Base64-encoded principal object |

### 3.3 Azure AD / MSAL Config

**File:** `MiBuddy-Backend/frontend/src/authConfig.ts`

```typescript
// authConfig.ts — Full file
export const msalConfig = {
    auth: {
        clientId:  "1994098f-d8c0-4ebe-bde0-b2fcc5db5fcb",            // Line 3
        authority: "https://login.microsoftonline.com/7a746742-...",    // Line 4
        redirectUri: window.location.origin + "/auth.html",            // Line 5
    },
    cache: {
        cacheLocation: "sessionStorage",                                // Line 8
        storeAuthStateInCookie: false,                                  // Line 9
    },
};

export const loginRequest = {
    scopes: ["User.Read", "Files.Read.All", "Sites.Read.All"]          // Line 14
};

export const graphConfig = {
    graphMeEndpoint: "https://graph.microsoft.com/v1.0/me",            // Line 18
};
```

**Backend Azure AD Config — File:** `MiBuddy-Backend/backend/utils/environ.py` — Lines 233-236

```python
# environ.py — Lines 233-236
AZURE_AD_CLIENT_ID     = os.environ.get("AZURE_AD_CLIENT_ID",     "1994098f-...")
AZURE_AD_CLIENT_SECRET = os.environ.get("AZURE_AD_CLIENT_SECRET", "cCb8Q~GDU...")
AZURE_AD_TENANT_ID     = os.environ.get("AZURE_AD_TENANT_ID",     "7a746742-...")
```

---

## 4. Backend Token Validation (All 3 Paths)

**File:** `MiBuddy-Backend/backend/auth/auth_utils.py` — Full file (62 lines)

```python
# auth_utils.py — Lines 7-62
def get_authenticated_user_details(request_headers):
    """
    Priority order:
      1. JWT Bearer token  →  MAS/OKTA users
      2. Azure EasyAuth headers  →  Motherson web users
      3. Dev sample_user  →  local development fallback
    """
    user_object = {}

    # ── PATH 1: JWT Bearer Token (Lines 18-39) ────────────────────
    auth_header = request_headers.get("authorization", "")             # Line 19
    if auth_header.lower().startswith("bearer "):                      # Line 20
        token = auth_header[7:].strip()                                # Line 21
        if token:
            try:
                from backend.utils.environ import YOUR_SECRET_KEY       # Line 24
                decoded = pyjwt.decode(                                 # Line 25
                    token, YOUR_SECRET_KEY, algorithms=["HS256"]
                )
                return {
                    "user_principal_id": decoded.get("UserId") or decoded.get("sub", ""),
                    "user_name":         decoded.get("email", ""),       # Line 28
                    "auth_provider":     decoded.get("auth_provider", "okta"),
                    "auth_token":        token,                         # Line 30
                    "client_principal_b64": "",
                    "aad_id_token":      "",
                    "domain":            decoded.get("Domain", ""),      # Line 33
                    "auth_type":         "jwt",                         # Line 34
                }
            except pyjwt.ExpiredSignatureError:                         # Line 36
                logger.warning("JWT rejected: token expired")
            except pyjwt.InvalidTokenError as exc:                      # Line 38
                logger.warning("JWT rejected: %s", exc)

    # ── PATH 2: Azure EasyAuth Headers (Lines 41-60) ──────────────
    principal_id = request_headers.get("x-ms-client-principal-id")     # Line 42

    if not principal_id:
        # ── PATH 3: Dev Fallback (Lines 44-53) ────────────────────
        from . import sample_user                                       # Line 46
        raw = sample_user.sample_user                                   # Line 47
        user_object["user_principal_id"] = raw["x-ms-client-principal-id"]
        user_object["user_name"]         = raw["x-ms-client-principal-name"]
        user_object["auth_provider"]     = raw["x-ms-client-principal-idp"]
        user_object["auth_token"]        = raw["x-ms-token-aad-id-token"]
        user_object["client_principal_b64"] = raw["x-ms-client-principal"]
        user_object["aad_id_token"]      = raw["x-ms-token-aad-id-token"]
    else:
        # Azure EasyAuth present
        user_object["user_principal_id"] = principal_id                 # Line 55
        user_object["user_name"]         = request_headers.get("x-ms-client-principal-name")
        user_object["auth_provider"]     = request_headers.get("x-ms-client-principal-idp")
        user_object["auth_token"]        = request_headers.get("x-ms-token-aad-id-token")
        user_object["client_principal_b64"] = request_headers.get("x-ms-client-principal")
        user_object["aad_id_token"]      = request_headers.get("x-ms-token-aad-id-token")

    return user_object                                                  # Line 62
```

---

## 5. Frontend — Token Storage & Injection

### 5.1 Token Storage

**File:** `MiBuddy-Backend/frontend/src/ProtectedRoute.tsx`

```typescript
// ProtectedRoute.tsx — Lines 54-62  (after OKTA callback)
if (masToken) {
    sessionStorage.setItem("masAccessToken", masToken);                // Line 55
    localStorage.setItem("authType", "mas");                           // Line 56
    localStorage.setItem("userId",   UserId || "mas-user");            // Line 57
    localStorage.setItem("domain",   Domain || "MAS");                 // Line 58
    localStorage.removeItem("unauthorized");                           // Line 59
    navigate("/", { replace: true });                                  // Line 60
    return;
}
```

| Storage Key | Location | Value |
|-------------|----------|-------|
| `masAccessToken` | sessionStorage | The signed JWT token |
| `authType` | localStorage | `"mas"` |
| `userId` | localStorage | OKTA sub or `"mas-user"` |
| `domain` | localStorage | Email domain or `"MAS"` |
| `accessToken` | localStorage | Legacy login token |

### 5.2 getMASToken() — Retrieve Token

**File:** `MiBuddy-Backend/frontend/src/ProtectedRoute.tsx` — Lines 17-19

```typescript
// ProtectedRoute.tsx — Lines 17-19
export function getMASToken(): string | null {
    return sessionStorage.getItem("masAccessToken");
}
```

### 5.3 getAuthHeaders() — Inject Token into API Calls

**File:** `MiBuddy-Backend/frontend/src/ProtectedRoute.tsx` — Lines 25-30

```typescript
// ProtectedRoute.tsx — Lines 25-30
export function getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = getMASToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
}
```

**How this is used in API calls (POST, GET, PATCH):**

```typescript
// Example: Any API call in the app
const response = await fetch("/api/some-endpoint", {
    method: "POST",                          // or GET, PATCH, DELETE
    headers: getAuthHeaders(),               // ← injects Bearer token
    body: JSON.stringify(payload),
});

// getAuthHeaders() returns:
// {
//   "Content-Type": "application/json",
//   "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."    ← only if MAS user
// }
```

### 5.4 ProtectedRoute — Full Auth Guard Flow

**File:** `MiBuddy-Backend/frontend/src/ProtectedRoute.tsx` — Lines 48-129

```typescript
// ProtectedRoute.tsx — Lines 48-129
useEffect(() => {
    const authenticate = async () => {
        const params = new URLSearchParams(window.location.search);
        const masToken = params.get("mas_token");
        const UserId = params.get("userid") || localStorage.getItem("userId");
        const Domain = params.get("domain") || localStorage.getItem("domain");
        const isMASUser = MAS_WIN_DOMAINS.includes(Domain?.toLowerCase() || "");

        // ── CASE 1: Returning from OKTA with token (Lines 54-62) ──
        if (masToken) {
            sessionStorage.setItem("masAccessToken", masToken);
            localStorage.setItem("authType", "mas");
            localStorage.setItem("userId", UserId || "mas-user");
            localStorage.setItem("domain", Domain || "MAS");
            navigate("/", { replace: true });     // Strip token from URL
            return;
        }

        // ── CASE 2: MAS user, check existing token (Lines 67-78) ──
        if (isMASUser) {
            const storedToken = getMASToken();
            if (storedToken) {
                setLoading(false);                // Token exists, allow access
                return;
            }
            window.location.href = "/auth/mas/start";  // No token → OKTA login
            return;
        }

        // ── CASE 3: Standard Motherson user (Lines 81-125) ────────
        if (!UserId || !Domain) {
            console.warn("Missing userid or domain");
            setLoading(false);
            return;
        }

        const response = await fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ UserName: UserId, Domain: Domain }),
        });
        // ... handle response
    };
    authenticate();
}, []);
```

---

## 6. Legacy Login Page

**File:** `MiBuddy-Backend/frontend/src/pages/login/Login.tsx`

```typescript
// Login.tsx — Lines 8-27  (loginUser function)
async function loginUser(credentials: any) {
    const userinfo = credentials.username;
    const domain = userinfo.split("\\")[0];      // "DOMAIN\\username" format
    const uname = userinfo.split("\\")[1];

    return fetch("https://genie-uat.motherson.com/login", {           // Line 19
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            username: uname,
            password: credentials.password,
            domain: domain,
        }),
    }).then((data) => data.json());
}

// Login.tsx — Lines 69-96  (handleSubmit)
const handleSubmit = async (e: any) => {
    loginUser({ username, password }).then((response) => {
        if ("token" in response) {
            localStorage.setItem("accessToken", response["token"]);    // Line 77
            const decodedToken = parseJwt(response["token"]);          // Line 78
            const userId = decodedToken?.sub;
            const domain = decodedToken?.domain;

            localStorage.setItem("userId", userId);                    // Line 82
            localStorage.setItem("domain", domain);                    // Line 85

            // Send token to backend                                   // Line 88
            fetch("http://127.0.0.1:5000/receive_token", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    token: { UserId: userId, Domain: domain }
                }),
            });
        }
    });
};
```

### 6.1 /receive_token Endpoint

**File:** `MiBuddy-Backend/app.py` — Lines 442-450

```python
# app.py — Lines 442-450
@app.post("/receive_token")
async def receive_token(request: Request):
    global localStorage                                                # Line 444
    data = await request.json()                                        # Line 445
    token = data.get("token")                                          # Line 446
    if not token:
        return JSONResponse(content={"error": "Token missing"}, status_code=400)
    localStorage = token                                               # Line 449
    return "Token Received"
```

---

## 7. Platform Pages — Frontend Routes

**File:** `MiBuddy-Backend/frontend/src/index.tsx` — Lines 74-99

```typescript
// index.tsx — Lines 74-99
<BrowserRouter>
  <Routes>
    {/* Main chat — PROTECTED */}
    <Route path="/" element={                                          // Line 77
      <ProtectedRoute>
        <Chat mode={mode} setMode={setMode} />
      </ProtectedRoute>
    } />

    {/* Image generation — UNPROTECTED */}
    <Route path="/image"      element={<Chat mode={mode} setMode={setMode} />} />  // Line 84

    {/* Shared conversation — PUBLIC */}
    <Route path="/share/:id"  element={<ChatShare />} />               // Line 85

    {/* 404 page */}
    <Route path="/404page"    element={<NoPage />} />                  // Line 86
    <Route path="*"           element={<NoPage />} />                  // Line 87

    {/* Voice interaction — UNPROTECTED */}
    <Route path="/voice"      element={<Voice />} />                   // Line 88

    {/* NotebookLM — PROTECTED */}
    <Route path="/notebooklm" element={<NotebookLMPage />} />          // Line 89
  </Routes>
</BrowserRouter>
```

**MSAL Initialization — Lines 106-119:**

```typescript
// index.tsx — Lines 106-119
msalInstance.initialize().then(() => {
    msalInstance.handleRedirectPromise().then(() => {
        ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
            <React.StrictMode>
                <MsalProvider instance={msalInstance}>
                    <App />
                </MsalProvider>
            </React.StrictMode>
        );
    });
});
```

### 7.1 Page Component Files

| Page | File Path |
|------|-----------|
| Chat | `MiBuddy-Backend/frontend/src/pages/chat/Chat.tsx` |
| Chat Status | `MiBuddy-Backend/frontend/src/pages/chat/ChatStatus.tsx` |
| Layout | `MiBuddy-Backend/frontend/src/pages/layout/Layout.tsx` |
| Login | `MiBuddy-Backend/frontend/src/pages/login/Login.tsx` |
| 404 Page | `MiBuddy-Backend/frontend/src/pages/NoPage.tsx` |
| Unauthorized | `MiBuddy-Backend/frontend/src/pages/Notauthorize.tsx` |
| NotebookLM | `MiBuddy-Backend/frontend/src/pages/Notebook/Notebooklm.tsx` |

---

## 8. Backend API Endpoints

**File:** `MiBuddy-Backend/app.py`

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/` | GET | Serve React app | Yes |
| `/login` | POST | Validate user (Azure Table) | No |
| `/auth/mas/start` | GET | Initiate OKTA login | No |
| `/authorization-code/callback` | GET | OKTA callback handler | CSRF state |
| `/receive_token` | POST | Store token from frontend | No |
| `/.auth/me` | GET | Get current user info | Yes |
| `/conversation` | POST | Chat API | Yes |
| `/conversation/cot` | POST | Chain-of-thought reasoning | Yes |
| `/history/list` | GET | List chat history | Yes |
| `/history/read` | POST | Read conversation | Yes |
| `/history/generate` | POST | Generate AI response | Yes |
| `/history/update` | POST | Update messages | Yes |
| `/history/delete` | DELETE | Delete conversation | Yes |
| `/history/archive` | POST | Archive conversation | Yes |
| `/sharepoint/validate_token` | POST | Validate SharePoint token | Yes |
| `/outlook/validate_token` | POST | Validate Outlook token | Yes |
| `/user/model` | POST/GET | User model preference | Yes |
| `/feedback` | POST | Submit feedback | Yes |
| `/notebooklm` | GET | NotebookLM page | Yes |

---

## 9. CORS Configuration

**File:** `MiBuddy-Backend/app.py` — Lines 218-225

```python
# app.py — Lines 218-225
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # Line 220 — WARNING: accepts all origins
    allow_credentials=True,         # Line 221
    allow_methods=["*"],            # Line 222
    allow_headers=["*"],            # Line 223
)
```

---

## 10. Complete Auth Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COMPLETE AUTH FLOW                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  STEP 1: Frontend Detects User Type                                 │
│  ProtectedRoute.tsx (Line 52)                                       │
│  ┌──────────────────────────────────────────────────┐               │
│  │ const isMASUser = MAS_WIN_DOMAINS.includes(Domain)│               │
│  └────────────────────┬─────────────────────────────┘               │
│                       │                                              │
│          ┌────────────┴────────────┐                                 │
│          ▼                         ▼                                 │
│  ┌───────────────┐        ┌────────────────┐                        │
│  │  MAS User     │        │ Standard User  │                        │
│  │  (OKTA Flow)  │        │ (EasyAuth Flow)│                        │
│  └───────┬───────┘        └────────┬───────┘                        │
│          │                         │                                 │
│  STEP 2A: OKTA                STEP 2B: EasyAuth                     │
│          │                         │                                 │
│  GET /auth/mas/start          POST /login                           │
│  app.py:536                   app.py:494                            │
│          │                         │                                 │
│  → Redirect to OKTA           → Check Azure Table                   │
│  → User authenticates          → Return {Message: true}             │
│          │                         │                                 │
│  GET /authorization-code/      → Store userId, domain               │
│       callback                     in localStorage                  │
│  app.py:569                        │                                │
│          │                         │                                 │
│  → Exchange code for token    ┌────┴──────────────────┐             │
│  → Fetch OKTA user info       │ Azure App Service     │             │
│  → Validate email domain      │ injects EasyAuth      │             │
│  → Sign MiBuddy JWT (8hr)     │ headers automatically │             │
│  → Redirect: /?mas_token=JWT  └───────────────────────┘             │
│          │                                                          │
│  Frontend stores JWT                                                │
│  sessionStorage["masAccessToken"]                                   │
│  ProtectedRoute.tsx:55                                              │
│                                                                     │
│  STEP 3: API Calls (Both Flows)                                     │
│  ┌──────────────────────────────────────────────┐                   │
│  │  getAuthHeaders()  — ProtectedRoute.tsx:25   │                   │
│  │                                              │                   │
│  │  if (MAS user):                              │                   │
│  │    headers["Authorization"] = "Bearer <JWT>" │                   │
│  │  else:                                       │                   │
│  │    Azure EasyAuth headers auto-injected      │                   │
│  └──────────────────────┬───────────────────────┘                   │
│                         │                                            │
│  STEP 4: Backend Validates                                          │
│  ┌──────────────────────┴───────────────────────┐                   │
│  │  auth_utils.py:7                             │                   │
│  │  get_authenticated_user_details()            │                   │
│  │                                              │                   │
│  │  Priority 1: Decode JWT Bearer token         │                   │
│  │  Priority 2: Read Azure EasyAuth headers     │                   │
│  │  Priority 3: Use dev sample_user             │                   │
│  └──────────────────────────────────────────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: File Index

### Session 1 — Governance Files

| File | Path | Key Content |
|------|------|-------------|
| permissions.py | `src/backend/base/agentcore/services/auth/permissions.py` | Role definitions (L147-367), Redis cache (L372-447), Permission version (L369) |
| decorators.py | `src/backend/base/agentcore/services/auth/decorators.py` | PermissionChecker class (L9-54) |
| roles.py | `src/backend/base/agentcore/api/roles.py` | Role CRUD API endpoints |
| _rbac_helpers.py | `src/backend/base/agentcore/components/models/_rbac_helpers.py` | Membership queries (L91-141), Access checks (L200-372) |
| organization/model.py | `src/.../models/organization/model.py` | Org model (L21-63) |
| department/model.py | `src/.../models/department/model.py` | Dept model (L14-48) |
| user_organization_membership/model.py | `src/.../models/user_organization_membership/model.py` | Org membership (L8-32) |
| user_department_membership/model.py | `src/.../models/user_department_membership/model.py` | Dept membership (L8-38) |
| approval_request/model.py | `src/.../models/approval_request/model.py` | Agent approval model (L28-138) |
| model_approval_request/model.py | `src/.../models/model_approval_request/model.py` | Model approval model (L19-74) |
| mcp_approval_request/model.py | `src/.../models/mcp_approval_request/model.py` | MCP approval model (L12-59) |
| approvals.py | `src/backend/base/agentcore/api/approvals.py` | Approval API: access control (L761-845), approve handler (L1396-1599) |
| approval_notifications.py | `src/backend/base/agentcore/services/approval_notifications.py` | Notification upsert (L13-51), root notify (L54-84) |

### Session 2 — Auth & Platform Files

| File | Path | Key Content |
|------|------|-------------|
| app.py | `MiBuddy-Backend/app.py` | /login (L494), /auth/mas/start (L536), OKTA callback (L569), CORS (L218) |
| auth_utils.py | `MiBuddy-Backend/backend/auth/auth_utils.py` | Token validation 3-path priority (L7-62) |
| environ.py | `MiBuddy-Backend/backend/utils/environ.py` | JWT secrets (L186-187), OKTA config (L254-256), Azure AD (L233-236) |
| ProtectedRoute.tsx | `MiBuddy-Backend/frontend/src/ProtectedRoute.tsx` | getMASToken (L17), getAuthHeaders (L25), Auth guard (L48-129) |
| Login.tsx | `MiBuddy-Backend/frontend/src/pages/login/Login.tsx` | Legacy login form (L69-96), loginUser (L8-27) |
| index.tsx | `MiBuddy-Backend/frontend/src/index.tsx` | Routes (L74-99), MSAL init (L106-119) |
| authConfig.ts | `MiBuddy-Backend/frontend/src/authConfig.ts` | Azure AD MSAL config |
