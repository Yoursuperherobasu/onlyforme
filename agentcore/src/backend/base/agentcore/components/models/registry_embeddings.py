"""Unified Embeddings component that reads models from the model_registry table (model_type='embedding').

All embedding invocations are delegated to the Model microservice via
``MicroserviceEmbeddings`` — no provider SDKs are imported here.
"""

import asyncio
import os
import threading
from uuid import UUID

from loguru import logger

from agentcore.base.embeddings.model import LCEmbeddingsModel
from agentcore.field_typing import Embeddings
from agentcore.io import DropdownInput, IntInput

# Display label → DB key mapping (same as LLM registry)
PROVIDER_LABEL_TO_KEY = {
    "OpenAI": "openai",
    "Azure": "azure",
    "Google": "google",
    "Custom Model": "openai_compatible",
}
PROVIDER_KEY_TO_LABEL = {v: k for k, v in PROVIDER_LABEL_TO_KEY.items()}
PROVIDER_OPTIONS = list(PROVIDER_LABEL_TO_KEY.keys())


def _fetch_embedding_models_for_provider(provider: str, user_id: str | None = None) -> list[str]:
    """Fetch active embedding models from the registry filtered by provider.

    Returns a list of strings formatted as 'display_name | model_name | uuid'.
    """
    if not provider:
        return []
    try:
        from agentcore.services.deps import get_db_service

        db_service = get_db_service()

        async def _query():
            from sqlalchemy import select

            from agentcore.services.database.models.model_registry.model import ModelRegistry
            from agentcore.services.database.models.user.model import User
            from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
            from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership

            async with db_service.with_session() as session:
                uid = _current_user_id(user_id)
                normalized_role = ""
                username = ""
                org_ids: set[UUID] = set()
                dept_ids: set[UUID] = set()
                if uid is not None:
                    user_row = await session.get(User, uid)
                    normalized_role = str(getattr(user_row, "role", "") or "").strip().lower()
                    username = str(getattr(user_row, "username", "") or "")
                    org_rows = (
                        await session.execute(
                            select(UserOrganizationMembership.org_id).where(
                                UserOrganizationMembership.user_id == uid,
                                UserOrganizationMembership.status.in_(["accepted", "active"]),
                            )
                        )
                    ).scalars().all()
                    dept_rows = (
                        await session.execute(
                            select(UserDepartmentMembership.department_id).where(
                                UserDepartmentMembership.user_id == uid,
                                UserDepartmentMembership.status == "active",
                            )
                        )
                    ).scalars().all()
                    org_ids = {r for r in org_rows if r is not None}
                    dept_ids = {r for r in dept_rows if r is not None}
                stmt = (
                    select(ModelRegistry)
                    .where(ModelRegistry.is_active.is_(True))
                    .where(ModelRegistry.approval_status == "approved")
                    .where(ModelRegistry.provider == provider)
                    .where(ModelRegistry.model_type == "embedding")
                    .order_by(ModelRegistry.display_name)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                if uid is not None and normalized_role != "root":
                    uid_str = str(uid)
                    filtered: list[ModelRegistry] = []
                    for row in rows:
                        visibility = str(getattr(row, "visibility_scope", "private") or "private").lower()
                        public_dept_ids = {str(v) for v in (getattr(row, "public_dept_ids", None) or [])}
                        if normalized_role == "super_admin" and row.org_id and row.org_id in org_ids:
                            filtered.append(row)
                            continue
                        if normalized_role == "department_admin" and row.dept_id and row.dept_id in dept_ids:
                            filtered.append(row)
                            continue
                        if normalized_role == "department_admin" and public_dept_ids.intersection({str(v) for v in dept_ids}):
                            filtered.append(row)
                            continue
                        if visibility == "private":
                            if (
                                str(getattr(row, "created_by_id", "") or "") == uid_str
                                or str(getattr(row, "requested_by", "") or "") == uid_str
                                or str(getattr(row, "created_by", "") or "") == username
                            ):
                                filtered.append(row)
                        elif visibility == "department":
                            if row.dept_id and row.dept_id in dept_ids:
                                filtered.append(row)
                            elif public_dept_ids.intersection({str(v) for v in dept_ids}):
                                filtered.append(row)
                        elif visibility == "organization":
                            if row.org_id and row.org_id in org_ids:
                                filtered.append(row)
                    rows = filtered
                return [f"{r.display_name} | {r.model_name} | {r.id}" for r in rows]

        return _run_async(_query())
    except Exception as e:
        logger.warning(f"Could not fetch registry embeddings for provider {provider}: {e}")
        return []


def _current_user_id(user_id: str | None = None) -> UUID | None:
    raw = user_id or os.getenv("AGENTCORE_USER_ID") or os.getenv("USER_ID")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except Exception:
        return None


def _get_registry_config(model_id: str, user_id: str | None = None) -> dict | None:
    """Fetch embedding model config using a dedicated sync engine."""
    from uuid import UUID

    from sqlalchemy.orm import Session

    from agentcore.services.database.models.model_registry.model import ModelRegistry
    from agentcore.services.database.models.user.model import User
    from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
    from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership
    from agentcore.utils.crypto import decrypt_api_key

    try:
        engine = _get_sync_engine()
        with Session(engine) as session:
            row = session.get(ModelRegistry, UUID(model_id))
            if row is None:
                logger.warning(f"Embedding model {model_id} not found in DB via sync engine")
                return None
            uid = _current_user_id(user_id)
            if uid is not None:
                user_row = session.get(User, uid)
                normalized_role = str(getattr(user_row, "role", "") or "").strip().lower()
                if normalized_role != "root":
                    username = str(getattr(user_row, "username", "") or "")
                    org_ids = {
                        r[0]
                        for r in session.query(UserOrganizationMembership.org_id)
                        .filter(
                            UserOrganizationMembership.user_id == uid,
                            UserOrganizationMembership.status.in_(["accepted", "active"]),
                        )
                        .all()
                        if r and r[0] is not None
                    }
                    dept_ids = {
                        r[0]
                        for r in session.query(UserDepartmentMembership.department_id)
                        .filter(
                            UserDepartmentMembership.user_id == uid,
                            UserDepartmentMembership.status == "active",
                        )
                        .all()
                        if r and r[0] is not None
                    }
                    visibility = str(getattr(row, "visibility_scope", "private") or "private").lower()
                    public_dept_ids = {str(v) for v in (getattr(row, "public_dept_ids", None) or [])}
                    uid_str = str(uid)
                    allowed = False
                    if normalized_role == "super_admin" and row.org_id and row.org_id in org_ids:
                        allowed = True
                    elif normalized_role == "department_admin" and row.dept_id and row.dept_id in dept_ids:
                        allowed = True
                    elif normalized_role == "department_admin" and public_dept_ids.intersection({str(v) for v in dept_ids}):
                        allowed = True
                    elif visibility == "private":
                        allowed = (
                            str(getattr(row, "created_by_id", "") or "") == uid_str
                            or str(getattr(row, "requested_by", "") or "") == uid_str
                            or str(getattr(row, "created_by", "") or "") == username
                        )
                    elif visibility == "department":
                        allowed = bool(
                            (row.dept_id and row.dept_id in dept_ids)
                            or public_dept_ids.intersection({str(v) for v in dept_ids})
                        )
                    elif visibility == "organization":
                        allowed = bool(row.org_id and row.org_id in org_ids)
                    if not allowed:
                        raise ValueError("Access denied to selected embedding model due to RBAC scope")

            enc_key = os.getenv("MODEL_REGISTRY_ENCRYPTION_KEY", "")
            if not enc_key:
                import base64
                import hashlib

        results = fetch_registry_models(provider=provider, model_type="embedding")
        return [
            f"{r['display_name']} | {r['model_name']} | {r['id']}"
            for r in results
        ]
    except Exception as e:
        logger.warning(f"Failed to fetch embeddings via microservice: {e}")
        return []


class RegistryEmbeddingsComponent(LCEmbeddingsModel):
    """A unified Embeddings component that dynamically loads models from the Model Registry.

    Users onboard embedding models via the Model Registry page. This component
    lets them pick a provider, then select a registered embedding model.
    """

    display_name: str = "Embeddings Model"
    description: str = "Select a provider and embedding model from the Model Registry."
    icon = "Binary"
    name = "RegistryEmbeddingsComponent"
    priority = 0

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Provider",
            info="Select the AI provider. Embedding models onboarded for this provider will appear below.",
            options=PROVIDER_OPTIONS,
            value="",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="registry_model",
            display_name="Registry Model",
            info="Select an embedding model from the Model Registry.",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="Override output embedding dimensions. Leave empty for model default.",
            advanced=True,
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Refresh dropdowns when provider changes or registry_model refresh is clicked."""
        current_user_id = str(
            getattr(self, "user_id", None)
            or getattr(getattr(self, "graph", None), "user_id", None)
            or ""
        ).strip() or None
        if field_name == "provider":
            provider_key = PROVIDER_LABEL_TO_KEY.get(field_value, field_value)
            try:
                options = _fetch_embedding_models_for_provider(provider_key, user_id=current_user_id)
                build_config["registry_model"]["options"] = options if options else []
                build_config["registry_model"]["value"] = options[0] if options else ""
            except Exception as e:
                logger.warning(f"Error fetching embeddings for provider {provider_key}: {e}")
                build_config["registry_model"]["options"] = []
                build_config["registry_model"]["value"] = ""

        elif field_name == "registry_model":
            provider_label = build_config.get("provider", {}).get("value", "")
            provider_key = PROVIDER_LABEL_TO_KEY.get(provider_label, provider_label)
            if provider_key:
                try:
                    options = _fetch_embedding_models_for_provider(provider_key, user_id=current_user_id)
                    build_config["registry_model"]["options"] = options if options else []
                    if options and not build_config["registry_model"].get("value"):
                        build_config["registry_model"]["value"] = options[0]
                except Exception as e:
                    logger.warning(f"Error refreshing registry embeddings: {e}")
                    build_config["registry_model"]["options"] = []

        return build_config

    def build_embeddings(self) -> Embeddings:
        """Build a MicroserviceEmbeddings proxy that delegates to the Model microservice."""
        from agentcore.services.model_service_client import MicroserviceEmbeddings, _get_model_service_settings

        selected = self.registry_model
        if not selected:
            msg = "No model selected. Please select a model from the Registry Model dropdown."
            raise ValueError(msg)

        parts = [p.strip() for p in selected.split("|")]
        if len(parts) < 3:
            msg = f"Invalid registry model format: {selected}. Please refresh the dropdown."
            raise ValueError(msg)

        model_name = parts[1]
        model_id = parts[2]

        current_user_id = str(
            getattr(self, "user_id", None)
            or getattr(getattr(self, "graph", None), "user_id", None)
            or ""
        ).strip() or None
        config = _get_registry_config(model_id, user_id=current_user_id)
        if config is None:
            msg = f"Embedding model {model_id} not found in registry or has been deleted."
            raise ValueError(msg)

        provider_label = self.provider or ""
        provider_key = PROVIDER_LABEL_TO_KEY.get(provider_label, provider_label).lower()

        dimensions = self.dimensions if self.dimensions not in (None, "") else None
        if dimensions is not None:
            dimensions = int(dimensions)

        return MicroserviceEmbeddings(
            service_url=service_url,
            service_api_key=service_api_key,
            provider=provider_key,
            model=model_name,
            registry_model_id=model_id,
            dimensions=dimensions,
        )
