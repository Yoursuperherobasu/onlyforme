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
   └─ Views approval → _get_approval_for_view() → al lowed (is request_to)
   └─ Approves → _get_approval_for_action() → allowed

3. POST-APPROVAL
   └─ AgentDeploymentProd.status = APPROVED
   └─ Guardrails promoted from UAT → 
   




   
   └─ Pinecone vectors copied: namespace → namespace_prod_v1
   └─ Developer notified via ApprovalNotification

4. TENANT ISOLATION GUARANTEE
   └─ Super admin from Org O2 CANNOT see/approve Org O1's agents
   └─ Dept admin from D2 CANNOT act on D1's approvals
   └─ Enforced at DB level via WHERE clauses on org_id/dept_id
```

---
---

# SESSION 2: Authentication (AgentCore Backend)

---

## 1. Authentication Architecture — 4 Token Sources

The agentcore backend is a FastAPI service. Every protected request is gated by a single dependency, `get_current_user`, which resolves the caller's identity from one of four sources, in order:

```
┌──────────────────────────────────────────────────────────────────┐
│                    INCOMING REQUEST                              │
│                                                                  │
│  ┌─────────────┐  ┌────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Source 1:   │  │ Source 2:  │  │ Source 3:   │  │ Source 4:│ │
│  │ Cookie      │  │ Bearer     │  │ Service     │  │ (none)   │ │
│  │ access_     │  │ header     │  │ API key     │  │ → 401    │ │
│  │ token_ag    │  │ (Swagger)  │  │ x-api-key   │  │          │ │
│  │ (Priority 1)│  │(Priority 2)│  │(Priority 3) │  │          │ │
│  └─────────────┘  └────────────┘  └─────────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

| Source | Who uses it | Trigger | Token type |
|--------|-------------|---------|------------|
| Cookie `access_token_ag` | Browser users (default) | Set after `/login` or `/azure/sso` | HS256 JWT (1 hr) |
| `Authorization: Bearer …` | Swagger / external API consumers | Header pasted manually | HS256 JWT (1 hr) |
| `x-api-key` header/query | Service-to-service (region gateway) | Static API key | Currently disabled, migrating to Azure Key Vault |
| None | — | — | `401 Could not validate credentials` |

There are **two login paths** that produce these tokens:
1. **Username + password** → `POST /login` (form-based)
2. **Azure SSO (Entra ID)** → `POST /azure/sso` (OIDC `idToken` from MSAL)

There is **no self-signup endpoint** — users are created either by an admin via `POST /users` or auto-provisioned on first Azure SSO login.

---

## 2. Username/Password Login Flow

### 2.1 Login Endpoint

**File:** `src/backend/base/agentcore/api/login.py` — Lines 164-199

```python
# login.py — Lines 164-199
@router.post("/login", response_model=AzureSSOResponse)
async def login_to_get_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],   # form-encoded
    db: DbSession,
):
    auth_settings = get_settings_service().auth_settings
    user = await authenticate_user(form_data.username,
                                   form_data.password, db)        # Line 172
    if user:
        tokens = await create_user_tokens(
            user_id=user.id, db=db, update_last_login=True,
        )                                                          # Line 182
        _apply_auth_cookies(response, tokens, auth_settings, user) # Line 183
        current_role = normalize_role(getattr(user, "role", "developer"))
        permissions = await get_permissions_for_role(current_role) # Line 185
        return {**tokens, "role": current_role, "permissions": permissions}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

### 2.2 authenticate_user() — Credential Verification

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 502-532

```python
# utils.py — Lines 502-532
async def authenticate_user(username: str, password: str,
                            db: AsyncSession) -> User | None:
    user = await get_user_by_username(db, username)
    if not user:
        return None

    # Auto-deactivate accounts past their expires_at timestamp
    if user.expires_at is not None:
        now = datetime.now(timezone.utc)
        expires_at = user.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now >= expires_at:
            user.is_active = False                           # ← side-effect
            db.add(user)
            await db.commit()
            raise HTTPException(401, "User account has expired")

    if not user.is_active:
        if not user.last_login_at:
            raise HTTPException(400, "Waiting for approval")
        raise HTTPException(401, "Inactive user")

    return user if verify_password(password, user.password) else None
```

Three failure modes besides "wrong password":
- **Expired account** → 401 + auto-deactivate
- **Inactive but never logged in** → 400 "Waiting for approval"
- **Inactive after first login** → 401 "Inactive user"

### 2.3 Cookie Application — `_apply_auth_cookies()`

**File:** `src/backend/base/agentcore/api/login.py` — Lines 42-73

```python
# login.py — Lines 42-73
def _apply_auth_cookies(response: Response, tokens: dict,
                        auth_settings, user: User) -> None:
    persistent_cookie = bool(tokens.get("persistent_cookie", True))
    access_expires  = tokens.get("access_expires_in")  if persistent_cookie else None
    refresh_expires = tokens.get("refresh_expires_in") if persistent_cookie else None

    response.set_cookie("refresh_token_ag", tokens["refresh_token"],
        httponly=auth_settings.REFRESH_HTTPONLY,    # True  — JS can't read
        samesite=auth_settings.REFRESH_SAME_SITE,   # "lax"
        secure=auth_settings.REFRESH_SECURE,
        expires=refresh_expires,                    # 7 days default
        domain=auth_settings.COOKIE_DOMAIN)
    response.set_cookie("access_token_ag", tokens["access_token"],
        httponly=auth_settings.ACCESS_HTTPONLY,     # False — JS can read
        samesite=auth_settings.ACCESS_SAME_SITE,    # "lax"
        secure=auth_settings.ACCESS_SECURE,
        expires=access_expires,                     # 1 hour default
        domain=auth_settings.COOKIE_DOMAIN)
    response.set_cookie("apikey_tkn_ag", str(user.store_api_key),
        httponly=auth_settings.ACCESS_HTTPONLY,
        samesite=auth_settings.ACCESS_SAME_SITE,
        secure=auth_settings.ACCESS_SECURE,
        expires=None,                               # session cookie
        domain=auth_settings.COOKIE_DOMAIN)
```

| Cookie | TTL | httpOnly | Purpose |
|--------|-----|----------|---------|
| `access_token_ag` | 1 hr (configurable) | **false** | JWT access token — readable by JS so the axios interceptor can re-attach it to outgoing requests |
| `refresh_token_ag` | 7 days (configurable) | **true** | JWT refresh token — never exposed to JS, sent only to `/refresh` |
| `apikey_tkn_ag` | session | true | Component store API key |

---

## 3. Azure SSO Login Flow (Entra ID)

### 3.1 Endpoint

**File:** `src/backend/base/agentcore/api/login.py` — Lines 202-343

```python
# login.py — Lines 202-343 (key excerpts)
@router.post("/azure/sso", response_model=AzureSSOResponse)
async def azure_sso_login(body: AzureSSORequest, response: Response, db: DbSession):
    auth_settings = get_settings_service().auth_settings

    # ── Verify the idToken against Microsoft's JWKS ──
    payload = jwt.decode(
        body.idToken,
        jwks,                                                   # fetched from MS
        algorithms=["RS256"],                                   # Line 221
        audience=auth_settings.AZURE_CLIENT_ID,
        issuer=f"https://login.microsoftonline.com/"
               f"{auth_settings.AZURE_TENANT_ID}/v2.0",
    )

    email             = payload.get("preferred_username", "").lower()
    entra_object_id   = payload.get("oid")
    display_name      = payload.get("name")

    # ── Resolve or auto-provision user ──
    # Looks up by email or entra_object_id; if found, attaches entra_object_id;
    # if not found, creates a new User with role="developer" (or "root" if email
    # matches PLATFORM_ROOT_EMAIL).

    tokens = await create_user_tokens(user_id=user.id, db=db, update_last_login=True)
    _apply_auth_cookies(response, tokens, auth_settings, user)   # Line 336
    return {**tokens, "role": ..., "permissions": ...}
```

### 3.2 What "verify against JWKS" means

Azure publishes its public signing keys at:
```
https://login.microsoftonline.com/common/discovery/v2.0/keys
```

Backend:
1. Fetches the JWK matching the `kid` header on the idToken
2. Verifies the RS256 signature with that public key
3. Verifies `aud == AZURE_CLIENT_ID` and `iss` matches the tenant
4. Trusts the resulting claims

If any check fails → 401, no token issued.

### 3.3 Auto-provisioning rules

- **First-ever SSO login from `PLATFORM_ROOT_EMAIL`** → user is created with `role="root"`
- **Any other new email** → user is created with `role="developer"`, `is_active=True`
- **Existing user matched by email** → `entra_object_id` is attached so future logins resolve by oid
- **Existing user matched by entra_object_id** → that user is logged in (email is updated if changed)

This makes the *first* SSO login of the platform owner the bootstrap step that unlocks the rest of the access-control UI.

### 3.4 No other SSO providers

There is **no Okta, no Keycloak, no generic SAML, and no social login** in this codebase. Azure Entra ID is the only OIDC provider.

---

## 4. JWT Token System

### 4.1 Algorithm and Secret

- **Algorithm:** HS256 (HMAC-SHA-256, symmetric)
- **Secret source:** `auth_settings.SECRET_KEY` — comes from env var `AGENTCORE_SECRET_KEY` or, if unset, an auto-generated value persisted to `{CONFIG_DIR}/secret_key`

**File:** `src/backend/base/agentcore/services/settings/auth.py` — Lines 55-85 (key generation/persistence logic)

### 4.2 Token Creation — `create_token()`

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 289-302

```python
# utils.py — Lines 289-302
def create_token(data: dict, expires_delta: timedelta):
    settings_service = get_settings_service()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    to_encode["exp"] = expire
    to_encode["iat"] = int(now.timestamp())
    return jwt.encode(
        to_encode,
        settings_service.auth_settings.SECRET_KEY.get_secret_value(),
        algorithm=settings_service.auth_settings.ALGORITHM,    # "HS256"
    )
```

### 4.3 Token Pair Creation — `create_user_tokens()`

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 426-452

```python
# utils.py — Lines 426-452
async def create_user_tokens(user_id: UUID, db: AsyncSession, *,
                             update_last_login: bool = False) -> dict:
    access_seconds, refresh_seconds, persistent_cookie = (
        await _resolve_runtime_token_config(db)             # ← reads timeout_settings table
    )
    access_token_expires  = timedelta(seconds=access_seconds)
    access_token = create_token(
        data={"sub": str(user_id), "type": "access"},
        expires_delta=access_token_expires,
    )
    refresh_token_expires = timedelta(seconds=refresh_seconds)
    refresh_token = create_token(
        data={"sub": str(user_id), "type": "refresh"},
        expires_delta=refresh_token_expires,
    )
    # ... update last_login_at if requested
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_in":  access_seconds,
        "refresh_expires_in": refresh_seconds,
        "persistent_cookie": persistent_cookie,
        "token_type": "bearer",
    }
```

### 4.4 JWT Payload Structure

```json
{
  "sub":  "550e8400-e29b-41d4-a716-446655440000",
  "type": "access",
  "iat":  1714000000,
  "exp":  1714003600
}
// Algorithm: HS256
// Secret:    auth_settings.SECRET_KEY
```

There is **no email, role, or permission** baked into the JWT — the backend looks those up on every request from the DB / Redis cache. This means revoking a user's role takes effect immediately on the next request (no need to wait for token expiry).

### 4.5 Token TTL — Runtime Configurable

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 391-423

The default TTLs (1 hr access / 7 day refresh) come from `auth_settings`, but the `timeout_settings` table can override them at runtime:

| `timeout_settings` field | Maps to |
|---|---|
| `session_timeout` | access token TTL |
| `cookie_timeout` | refresh token TTL |
| `persistent_cookie` | whether cookies have an `Expires` attribute or are session-only |

Precedence: **DB row > env var > hardcoded default**. Admins can change session policy without redeploying.

---

## 5. Token Validation — `get_current_user`

### 5.1 The Top-Level Dependency

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 125-152

```python
# utils.py — Lines 125-152
async def get_current_user(
    token:        Annotated[str, Security(oauth2_login)],     # cookie or form
    bearer:       Annotated[object | None, Security(http_bearer)],
    query_param:  Annotated[str, Security(api_key_query)],
    header_param: Annotated[str, Security(api_key_header)],
    db:           Annotated[AsyncSession, Depends(get_session)],
    request:      Request,
) -> User:
    # 1. Try OAuth2 password-flow token (cookie or Swagger form login)
    if token:
        return await get_current_user_by_jwt(token, db)
    # 2. Try HTTPBearer token (paste in Swagger Authorize → Bearer)
    if bearer and hasattr(bearer, "credentials") and bearer.credentials:
        return await get_current_user_by_jwt(bearer.credentials, db)
    # 3. Try service-to-service API key
    raw_api_key = header_param or query_param
    if raw_api_key:
        service_user = _validate_service_api_key(raw_api_key)
        if service_user:
            return service_user
    raise HTTPException(401, "Could not validate credentials",
                        headers={"WWW-Authenticate": "Bearer"})
```

### 5.2 JWT Decoding — `get_current_user_by_jwt()`

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 155-236

```python
# utils.py — Lines 155-236
async def get_current_user_by_jwt(token: str, db: AsyncSession) -> User:
    settings_service = get_settings_service()
    secret_key = settings_service.auth_settings.SECRET_KEY.get_secret_value()

    payload = jwt.decode(
        token, secret_key,
        algorithms=[settings_service.auth_settings.ALGORITHM],   # HS256
    )
    user_id:    UUID      = payload.get("sub")
    token_type: str       = payload.get("type")
    token_iat:  int | None = payload.get("iat")

    # ── 1. Expiry check ──
    if expires := payload.get("exp"):
        if datetime.now(timezone.utc) > datetime.fromtimestamp(expires, timezone.utc):
            raise HTTPException(401, "Token has expired.")

    # ── 2. Revocation check (Redis) ──
    if await is_user_token_revoked(user_id, token_iat):          # Line 198
        raise HTTPException(401, "Token has been revoked.")

    # ── 3. DB lookup, active check ──
    user = await get_user_by_id(db, user_id)
    # ... validates user exists, is_active, not past expires_at

    return user
```

**Three layers of validation per request:** signature, expiry, revocation. Only after all three pass does the User row come back from the DB.

### 5.3 The Two Active-User Wrappers

**File:** `src/backend/base/agentcore/services/auth/utils.py` — Lines 265-276

```python
# utils.py — Lines 265-276
async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if not current_user.is_active:
        raise HTTPException(401, "Inactive user")
    return current_user

async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active or not current_user.is_superuser:
        raise HTTPException(403, "Insufficient privileges")
    return current_user
```

**Usage in API routes:**

```python
@router.get("/some-endpoint")
async def my_endpoint(current_user: CurrentActiveUser):    # alias of Depends(get_current_active_user)
    ...
```

These two dependencies are then composed with `PermissionChecker` (covered in Session 1, §1.3) to gate by both *identity* and *permissions*.

---

## 6. Token Revocation & Identity Blocklist

Both are Redis-backed runtime mechanisms that take effect *without* waiting for token expiry. They are enabled via env var `AUTH_REDIS_SECURITY_KEYS_ENABLED=true`.

### 6.1 Token Revocation

**File:** `src/backend/base/agentcore/services/auth/token_revocation.py` — Lines 1-43

```python
# token_revocation.py — Lines 23-37
async def revoke_user_tokens(user_id: UUID) -> None:
    if not _redis_auth_security_enabled(): return
    settings_service = get_settings_service()
    redis = get_redis_client(settings_service)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    await redis.set(_revocation_key(user_id), str(now_ts))   # auth:revoked_after:user:{id}

async def is_user_token_revoked(user_id: UUID, token_iat: int | None) -> bool:
    if not _redis_auth_security_enabled(): return False
    revoked_after_ts = int(revoked_after)
    token_iat_ts     = int(token_iat or 0)
    return token_iat_ts <= revoked_after_ts
```

**Mechanism:** every revocation stores a "revoked-after" timestamp in Redis under `auth:revoked_after:user:{user_id}`. On every JWT validation, the token's `iat` claim is compared against this timestamp — if the token was issued *before* revocation, it's rejected. This invalidates **all outstanding tokens** for that user in one Redis write.

### 6.2 Identity Blocklist

**File:** `src/backend/base/agentcore/services/auth/identity_blocklist.py` — Lines 25-48

```python
# identity_blocklist.py — Lines 25-48
async def block_identity(*, email: str | None = None,
                         entra_object_id: str | None = None) -> None:
    if not _redis_auth_security_enabled(): return
    redis = get_redis_client(get_settings_service())
    if email:
        await redis.set(_email_key(email), "1")              # auth:blocked:email:{email}
    if entra_object_id:
        await redis.set(_entra_key(entra_object_id), "1")    # auth:blocked:entra:{oid}

async def is_identity_blocked(*, email=None, entra_object_id=None) -> bool: ...
```

**Mechanism:** when a user is deleted, their email + Entra object ID are written to Redis. On the next Azure SSO attempt, those identities are checked *before* user lookup — preventing a deleted user from being silently re-provisioned by signing in again with the same Microsoft account.

### 6.3 Wired Together — `invalidate_user_auth()`

**File:** `src/backend/base/agentcore/services/auth/invalidation.py` — Lines 11-22

```python
# invalidation.py — Lines 11-22
async def invalidate_user_auth(user_id, *, email=None, entra_object_id=None):
    await revoke_user_tokens(user_id)                              # Line 19
    await block_identity(email=email, entra_object_id=entra_object_id)  # Line 20
    await user_cache.delete_user(str(user_id))                     # Line 21
```

This is the single function called by both the soft-delete and hard-delete user pipelines — it's how a "delete user" admin action becomes effective everywhere within the next request cycle.

---

## 7. User Lifecycle — Soft Delete, Hard Delete

### 7.1 Soft Delete

**File:** `src/backend/base/agentcore/services/auth/soft_delete.py` — Lines 89-186

```python
# soft_delete.py — Lines 89-186 (key actions)
async def soft_delete_user_hierarchy(db, target_user_id, *, actor_user_id=None):
    # 1. Cascade: also soft-delete users created by target, and members of
    #    departments/orgs owned by target.
    # 2. For EACH user in the cascade:
    await invalidate_user_auth(                                # Line 121
        user.id,
        email=user.email or user.username,
        entra_object_id=user.entra_object_id,
    )
    user.is_active = False                                     # Line 126
    user.deleted_at = now                                      # Line 127
    db.add(user)
    # 3. Mark related memberships as "inactive"
    # 4. Archive owned departments / suspend owned organizations
```

Reversible. Rows stay; auth is invalidated; tenant memberships are marked inactive.

### 7.2 Hard Delete

**File:** `src/backend/base/agentcore/services/auth/hard_delete.py` — Lines 34-89

```python
# hard_delete.py — Lines 34-89 (key actions)
async def hard_delete_user(db, user_id, *, delete_owned_organizations=True):
    # GUARD: cannot hard-delete root users
    # 1. invalidate_user_auth(...) — same triple-revocation as soft delete
    # 2. Delete owned org/dept rows
    # 3. Cascade-delete all rows referencing user.id across every table
    # 4. Delete the User row itself
```

Irreversible. Everything FK'd to that user goes too. Only callable by admins, and never on root.

---

## 8. Auth Settings & Configuration

**File:** `src/backend/base/agentcore/services/settings/auth.py` — Lines 15-86

Pydantic `AuthSettings` model. Key fields and their env-var overrides:

| Setting | Default | Env Var |
|---|---|---|
| `SECRET_KEY` | auto-generated, persisted to `{CONFIG_DIR}/secret_key` | `AGENTCORE_SECRET_KEY` |
| `ALGORITHM` | `"HS256"` | — |
| `ACCESS_TOKEN_EXPIRE_SECONDS` | `3600` (1 hr) | `AUTH_TOKEN_EXPIRE_SECONDS` |
| `REFRESH_TOKEN_EXPIRE_SECONDS` | `604800` (7 days) | — |
| `REFRESH_HTTPONLY` / `ACCESS_HTTPONLY` | `True` / `False` | … |
| `REFRESH_SAME_SITE` / `ACCESS_SAME_SITE` | `"lax"` / `"lax"` | … |
| `REFRESH_SECURE` / `ACCESS_SECURE` | `False` / `False` | … |
| `COOKIE_DOMAIN` | `None` (browser infers) | … |
| `AZURE_TENANT_ID` | — | `AZURE_TENANT_ID` |
| `AZURE_CLIENT_ID` | — | `AZURE_CLIENT_ID` |
| `PLATFORM_ROOT_EMAIL` | — | `PLATFORM_ROOT_EMAIL` |

**Password hashing** — Line 50:

```python
# auth.py — Line 50
pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

Bcrypt only. Hash via `get_password_hash(password)`, verify via `verify_password(plain, hashed)` — both in `services/auth/utils.py` lines 279-286.

---

## 9. User Model

**File:** `src/backend/base/agentcore/services/database/models/user/model.py` — Lines 24-63

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `username` | str | unique, indexed |
| `email` | str \| None | unique, indexed (nullable) |
| `password` | str | bcrypt hash |
| `display_name` | str \| None | |
| `entra_object_id` | str \| None | Azure `oid`; unique, indexed |
| `is_active` | bool | default `False` — admins flip this on |
| `is_superuser` | bool | platform-level admin |
| `role` | str | `"developer"` default; one of the 7 roles in Session 1 |
| `last_login_at` | datetime \| None | bumped by `create_user_tokens(update_last_login=True)` |
| `expires_at` | datetime \| None | optional sunset date — auto-deactivates on first auth attempt past this |
| `deleted_at` | datetime \| None | soft-delete tombstone |
| `store_api_key` | str \| None | issued for component-store access |

Note: `role` lives **on the user row** and is the single source for `permissions = await get_permissions_for_role(user.role)`. There is no per-user permission override table — to differ a user's permissions, you create a new role.

---

## 10. Refresh & Logout

### 10.1 Refresh Endpoint

**File:** `src/backend/base/agentcore/api/login.py` — Lines 345-373

```python
# login.py — Lines 345-373
@router.post("/refresh", response_model=AzureSSOResponse)
async def refresh_token(request: Request, response: Response, db: DbSession):
    auth_settings = get_settings_service().auth_settings
    token = request.cookies.get("refresh_token_ag")              # Line 353
    if token:
        tokens = await create_refresh_token(token, db)           # Line 354
        user_id = tokens.get("user_id")
        user = await get_user_by_id(db, user_id)
        _apply_auth_cookies(response, tokens, auth_settings, user)   # Line 363
        # returns new {access_token, refresh_token, role, permissions}
```

`create_refresh_token()` (utils.py:455) decodes the refresh token, validates it's not revoked / expired, and issues a fresh access+refresh pair. The frontend interceptor calls this automatically on a 401 (see §11.4).

### 10.2 Logout Endpoint

**File:** `src/backend/base/agentcore/api/login.py` — Lines 376-381

```python
# login.py — Lines 376-381
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token_ag")
    response.delete_cookie("access_token_ag")
    response.delete_cookie("apikey_tkn_ag")
    return {"message": "Logout successful"}
```

Note: this is a *cookie clear*, not a token revoke. The JWT itself remains technically valid until its `exp`. To actually invalidate it (e.g. account compromise), an admin must delete or deactivate the user, which calls `invalidate_user_auth()` and writes the revocation timestamp to Redis (see §6).

---

## 11. Frontend Authentication

### 11.1 Login Page

**File:** `src/frontend/src/pages/LoginPage/index.tsx`

Two paths in one form:

```tsx
// LoginPage — Azure SSO branch (~line 98)
const response = await instance.loginPopup(loginRequest);   // MSAL popup
const idToken  = response.idToken;
const res = await fetch("/api/azure/sso", {
    method: "POST",
    credentials: "include",                                  // ← cookies in/out
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }),
});
const data = await res.json();
login(data.access_token, data.role, data.permissions, data.refresh_token);
```

Username/password branch posts the form to `/api/login` via the `useLoginUser` hook. Both branches end with `login(...)` updating the AuthContext.

There's also a separate admin-only login at **`src/frontend/src/pages/AdminPage/LoginPage/index.tsx`** which is form-only (no Azure SSO) — used for the platform's bootstrapping admin.

### 11.2 Token Storage

The backend sets all tokens as cookies. The frontend doesn't store the JWT in localStorage in the standard flow — `withCredentials: true` on axios sends cookies automatically. However, because `access_token_ag` is `httpOnly: false`, the request interceptor *can* read it and re-attach it as a Bearer header (some endpoints expect the header form).

**Cookie helpers — File:** `src/frontend/src/utils/utils.ts` — Lines 1013-1024

```ts
// utils.ts — Lines 1013-1024
export const getAuthCookie = (cookies: Cookies, tokenName: string) =>
    cookies.get(tokenName);

export const setAuthCookie = (cookies: Cookies, tokenName: string, value: string) => {
    const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
    cookies.set(tokenName, value, {
        path: "/",
        secure: isHttps,
        sameSite: "lax",
    });
};
```

### 11.3 Axios Request Interceptor — Bearer Injection

**File:** `src/frontend/src/controllers/API/api.tsx` — Lines 209-244

```tsx
// api.tsx — Lines 209-244
const requestInterceptor = api.interceptors.request.use(async (config) => {
    const accessToken = customGetAccessToken();
    if (accessToken && !isAuthorizedURL(config?.url)) {
        config.headers["Authorization"] = `Bearer ${accessToken}`;
    }
    return config;
});
```

A parallel `fetch()` interceptor (lines 144-160) does the same for non-axios calls. External URLs (GitHub API, MS Graph, Segment, etc., lines 103-142) are skipped so we don't leak tokens to third parties.

### 11.4 Response Interceptor — Auto-Refresh on 401

**File:** `src/frontend/src/controllers/API/api.tsx` — Lines 162-207, 272-301

```tsx
// api.tsx — Lines 167-175
async (error: AxiosError) => {
    const statusCode = error?.response?.status;
    const isAuthenticationError = statusCode === 401;
    const shouldRetryRefresh = isAuthenticationError &&
                               !isAuthEndpoint(error?.config?.url);
    if (shouldRetryRefresh) {
        const retriedResponse = await tryToRenewAccessToken(error);
        if (retriedResponse) return retriedResponse;
    }
    // ...
}
```

`tryToRenewAccessToken()` (api.tsx:272-301):
1. Calls `POST /api/refresh` (deduplicated — multiple 401s race-share one refresh promise)
2. If successful → re-issues the original failed request with the fresh token
3. If failed → triggers logout and redirects to `/login`
4. After 3 consecutive failures, force-logs-out

### 11.5 AuthContext

**File:** `src/frontend/src/contexts/authContext.tsx` — Lines 1-268

Shape:
```ts
{
  accessToken: string | null,
  role:        string | null,
  permissions: string[],
  userData:    Users | null,
  login(accessToken, role, permissions, refreshToken?): void,
  getUser(): Promise<void>,    // calls /api/users/whoami to hydrate userData
}
```

`login(...)` updates context state and immediately calls `getUser()` to fetch the live `User` record (so `userData.is_superuser`, `userData.entra_object_id`, etc. are available beyond just the token claims).

### 11.6 Zustand Auth Store

**File:** `src/frontend/src/stores/authStore.ts` — Lines 1-70

Persistent global state mirror of AuthContext (so non-React code can read auth state):

```ts
// authStore.ts — Lines 48-56
logout: async () => {
    removeAuthCookie(cookies, AGENTCORE_ACCESS_TOKEN);
    removeAuthCookie(cookies, AGENTCORE_REFRESH_TOKEN);
    removeAuthCookie(cookies, AGENTCORE_API_TOKEN);
    removeLocalStorage(AGENTCORE_ACCESS_TOKEN);
    removeLocalStorage(AGENTCORE_REFRESH_TOKEN);
    set({ isAuthenticated: false, accessToken: null, /* ... */ });
}
```

Tracks `authenticationErrorCount` — after 3 consecutive 401s, the store force-logs-out.

### 11.7 Protected Route Guard

**File:** `src/frontend/src/components/authorization/authGuard/index.tsx` — Lines 27-151

Behavior:
1. Reads `isAuthenticated` from the Zustand store. If false → `<Navigate to="/login?redirect=…" replace />`.
2. **Proactive refresh** — parses the JWT's `exp` claim and schedules a refresh **15 seconds before expiry**, so a session never bounces a real user request.
3. Also refreshes on `window` focus and `document` visibilitychange (catches users coming back from a long inactive tab).
4. After 3 failed refresh attempts, force-logs-out.

```ts
// authGuard/index.tsx — Lines 11-22 (exp parsing)
const getAccessTokenExpEpoch = (token: string | undefined): number | null => {
    if (!token) return null;
    try {
        const payloadPart = token.split(".")[1];
        const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
        const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
        const payload = JSON.parse(atob(padded));
        return typeof payload?.exp === "number" ? payload.exp : null;
    } catch { return null; }
};
```

### 11.8 Logout Flow

**File:** `src/frontend/src/controllers/API/queries/auth/use-post-logout.ts` — Lines 11-51

```ts
// use-post-logout.ts — Lines 31-44
async function logoutUser(): Promise<any> {
    const res = await api.post(`${getURL("LOGOUT")}`);
    return res.data;
}
const mutation = mutate(["useLogout"], logoutUser, {
    onSuccess: () => clearClientAuthState(),    // wipe stores
    onError:   () => clearClientAuthState(),    // wipe stores even on failure
});
```

Crucially, `clearClientAuthState()` runs on both success and error — so a network failure to `/logout` doesn't trap the user in a "half-logged-in" UI.

---

## 12. Complete Authentication Flow Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                          LOGIN — TWO PATHS                             │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  PATH A: Username/Password           PATH B: Azure SSO                 │
│  ───────────────────────────         ───────────────────────────       │
│                                                                        │
│  LoginPage form submit               LoginPage Azure button            │
│         │                                    │                         │
│         ▼                                    ▼                         │
│  POST /login                         instance.loginPopup() (MSAL)      │
│  (form: username, password)                  │                         │
│         │                                    ▼                         │
│         ▼                            POST /azure/sso { idToken }       │
│  authenticate_user()                         │                         │
│  utils.py:502                                ▼                         │
│  • get_user_by_username                  jwt.decode(idToken,           │
│  • check expires_at                          jwks, RS256, …)           │
│  • check is_active                       login.py:218                  │
│  • verify_password (bcrypt)              • verify aud, iss             │
│         │                                • resolve / auto-provision    │
│         └────────────────┬───────────────┘                             │
│                          ▼                                             │
│            create_user_tokens()                                        │
│            utils.py:426                                                │
│            • access JWT  (1 hr,  HS256)                                │
│            • refresh JWT (7 day, HS256)                                │
│                          │                                             │
│                          ▼                                             │
│            _apply_auth_cookies()                                       │
│            login.py:42                                                 │
│            Set-Cookie: access_token_ag                                 │
│            Set-Cookie: refresh_token_ag (httpOnly)                     │
│            Set-Cookie: apikey_tkn_ag                                   │
│                          │                                             │
│                          ▼                                             │
│         Response { access_token, refresh_token,                        │
│                    role, permissions }                                 │
│                          │                                             │
│                          ▼                                             │
│         Frontend AuthContext.login(...)                                │
│         + Zustand store.setAuthContext({role, permissions})            │
│         + getUser() → /api/users/whoami                                │
│                          │                                             │
│                          ▼                                             │
│         Navigate to /agents (or ?redirect target)                      │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                          PROTECTED REQUEST                             │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  React component fires API call                                        │
│            │                                                           │
│            ▼                                                           │
│  Axios request interceptor (api.tsx:209)                               │
│  Authorization: Bearer <access_token_ag>                               │
│            │                                                           │
│            ▼ (cookies also auto-attached via withCredentials)          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Backend FastAPI dependency chain                          │        │
│  │                                                            │        │
│  │  Depends(get_current_active_user)                          │        │
│  │       └─ Depends(get_current_user)  utils.py:125           │        │
│  │             ├─ try cookie / OAuth2 form                    │        │
│  │             ├─ try HTTPBearer                              │        │
│  │             └─ try x-api-key                               │        │
│  │                  │                                         │        │
│  │                  ▼                                         │        │
│  │       get_current_user_by_jwt()  utils.py:155              │        │
│  │       1. jwt.decode(secret_key, HS256)                     │        │
│  │       2. exp not in past?                                  │        │
│  │       3. Redis: token not revoked?                         │        │
│  │       4. DB: user exists, is_active, not expired?          │        │
│  │                  │                                         │        │
│  │                  ▼                                         │        │
│  │       Return User object                                   │        │
│  │                  │                                         │        │
│  │  PermissionChecker(["..."])  decorators.py:9               │        │
│  │  ✓ user has the required permission?                       │        │
│  └────────────────────────────────────────────────────────────┘        │
│            │                                                           │
│            ▼                                                           │
│  Endpoint handler runs                                                 │
│            │                                                           │
│            ▼                                                           │
│  IF response.status == 401:                                            │
│       Frontend response interceptor (api.tsx:167)                      │
│       → tryToRenewAccessToken() → POST /api/refresh                    │
│       → retry original request                                         │
│       → after 3 failures: logout + redirect /login                     │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                       ADMIN DEACTIVATES A USER                         │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  POST /users/{id}/soft-delete                                          │
│            │                                                           │
│            ▼                                                           │
│  soft_delete_user_hierarchy()  soft_delete.py:89                       │
│            │                                                           │
│            ▼                                                           │
│  invalidate_user_auth()  invalidation.py:11                            │
│       1. revoke_user_tokens(user.id)                                   │
│          → Redis: auth:revoked_after:user:{id} = now()                 │
│       2. block_identity(email, entra_object_id)                        │
│          → Redis: auth:blocked:email:{email} = "1"                     │
│          → Redis: auth:blocked:entra:{oid}   = "1"                     │
│       3. user_cache.delete_user(id)                                    │
│            │                                                           │
│            ▼                                                           │
│  user.is_active = False, deleted_at = now                              │
│            │                                                           │
│            ▼                                                           │
│  EFFECT: next request from that user → JWT iat < revoked_after_ts      │
│          → 401 "Token has been revoked"                                │
│          → frontend interceptor → /api/refresh → also rejected         │
│          → logout + /login                                             │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 13. Backend API — Auth Endpoint Map

**File:** `src/backend/base/agentcore/api/login.py`

| Endpoint | Method | Line | Purpose | Auth Required |
|----------|--------|------|---------|---------------|
| `/login` | POST | 164 | Username/password login | No |
| `/azure/sso` | POST | 202 | Azure Entra ID SSO login | No (verifies idToken instead) |
| `/refresh` | POST | 345 | Issue new access/refresh pair | Refresh-token cookie required |
| `/logout` | POST | 376 | Clear auth cookies | No |

User-management endpoints (`POST /users`, `GET /users/whoami`, etc.) live in `api/users.py` and require `Depends(get_current_active_user)` plus appropriate permissions.

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

### Session 2 — Authentication Files

#### Backend

| File | Path | Key Content |
|------|------|-------------|
| login.py | `src/backend/base/agentcore/api/login.py` | `_apply_auth_cookies` (L42-73), `/login` (L164-199), `/azure/sso` (L202-343), `/refresh` (L345-373), `/logout` (L376-381) |
| utils.py | `src/backend/base/agentcore/services/auth/utils.py` | `get_current_user` (L125-152), `get_current_user_by_jwt` (L155-236), `get_current_active_user` (L265-276), `create_token` (L289-302), `create_user_tokens` (L426-452), `create_refresh_token` (L455), `authenticate_user` (L502-532) |
| token_revocation.py | `src/backend/base/agentcore/services/auth/token_revocation.py` | `revoke_user_tokens` (L23), `is_user_token_revoked` (L32) |
| identity_blocklist.py | `src/backend/base/agentcore/services/auth/identity_blocklist.py` | `block_identity` (L25), `is_identity_blocked` |
| invalidation.py | `src/backend/base/agentcore/services/auth/invalidation.py` | `invalidate_user_auth` (L11-22) — orchestrates all three revocations |
| soft_delete.py | `src/backend/base/agentcore/services/auth/soft_delete.py` | `soft_delete_user_hierarchy` (L89-186) |
| hard_delete.py | `src/backend/base/agentcore/services/auth/hard_delete.py` | `hard_delete_user` (L34-89) |
| service.py | `src/backend/base/agentcore/services/auth/service.py` | `AuthService` DI wrapper (L11) |
| auth.py (settings) | `src/backend/base/agentcore/services/settings/auth.py` | `AuthSettings`, secret-key persistence (L55-85), `pwd_context` bcrypt (L50) |
| user/model.py | `src/backend/base/agentcore/services/database/models/user/model.py` | `User` SQLModel (L24-63) |

#### Frontend

| File | Path | Key Content |
|------|------|-------------|
| LoginPage/index.tsx | `src/frontend/src/pages/LoginPage/index.tsx` | Username/password + Azure SSO form (L37+, MSAL popup ~L98) |
| AdminPage/LoginPage/index.tsx | `src/frontend/src/pages/AdminPage/LoginPage/index.tsx` | Admin-only username/password login (L18-84) |
| api.tsx | `src/frontend/src/controllers/API/api.tsx` | fetch interceptor (L144-160), response interceptor + 401 retry (L162-207), request interceptor (L209-244), `tryToRenewAccessToken` (L272-301) |
| authContext.tsx | `src/frontend/src/contexts/authContext.tsx` | `login`, `getUser`, `userData`, `accessToken`, `role`, `permissions` (L1-268) |
| authStore.ts | `src/frontend/src/stores/authStore.ts` | Zustand auth store, `logout` (L48-56) |
| authGuard/index.tsx | `src/frontend/src/components/authorization/authGuard/index.tsx` | Protected route, exp parsing (L11-22), proactive refresh (L27-151) |
| use-post-logout.ts | `src/frontend/src/controllers/API/queries/auth/use-post-logout.ts` | `useLogout` hook (L11-51) |
| utils.ts | `src/frontend/src/utils/utils.ts` | `getAuthCookie` / `setAuthCookie` (L1013-1024) |
