from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from loguru import logger

from agentcore.services.database.models.guardrail_catalogue.model import GuardrailCatalogue
from agentcore.services.deps import session_scope


@dataclass(slots=True)
class GuardrailExecutionResult:
    output_text: str
    action: str
    guardrail_id: str


@dataclass(slots=True)
class _CachedRails:
    cache_key: str
    rails: Any
    config_path: Path


_RAILS_CACHE: dict[str, _CachedRails] = {}
_RAILS_CACHE_LOCK = Lock()


def _to_uuid(value: str) -> UUID:
    try:
        return UUID(str(value))
    except Exception as exc:  # noqa: BLE001
        msg = f"Invalid guardrail id '{value}'. Expected a UUID."
        raise ValueError(msg) from exc


async def _get_guardrail(guardrail_id: UUID) -> GuardrailCatalogue:
    async with session_scope() as session:
        row = await session.get(GuardrailCatalogue, guardrail_id)

    if not row:
        msg = f"Guardrail {guardrail_id} was not found."
        raise ValueError(msg)

    if (row.status or "").lower() != "active":
        msg = f"Guardrail {guardrail_id} is not active."
        raise ValueError(msg)

    return row


def _extract_first_str(runtime_config: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = runtime_config.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _normalize_runtime_config(runtime_config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runtime_config, dict):
        msg = "Guardrail runtimeConfig must be a JSON object."
        raise ValueError(msg)

    config_yml = _extract_first_str(runtime_config, ("config_yml", "configYml", "config.yml"))
    rails_co = _extract_first_str(runtime_config, ("rails_co", "railsCo", "rails.co"))
    prompts_yml = _extract_first_str(runtime_config, ("prompts_yml", "promptsYml", "prompts.yml"))
    extra_files = runtime_config.get("files", {})

    if not config_yml:
        msg = "runtimeConfig must include 'config_yml' (or configYml/config.yml)."
        raise ValueError(msg)
    if not rails_co:
        msg = "runtimeConfig must include 'rails_co' (or railsCo/rails.co)."
        raise ValueError(msg)
    if extra_files is None:
        extra_files = {}
    if not isinstance(extra_files, dict):
        msg = "runtimeConfig 'files' must be an object of {relativePath: content}."
        raise ValueError(msg)

    return {
        "config_yml": config_yml,
        "rails_co": rails_co,
        "prompts_yml": prompts_yml,
        "files": extra_files,
    }


def is_nemo_runtime_config_ready(runtime_config: dict[str, Any] | None) -> bool:
    try:
        _normalize_runtime_config(runtime_config)
    except Exception:  # noqa: BLE001
        return False
    return True


def _write_safe_file(base_dir: Path, relative_path: str, content: str) -> None:
    if not relative_path or relative_path.strip() in {".", ".."}:
        msg = f"Invalid runtimeConfig file path: '{relative_path}'"
        raise ValueError(msg)

    base_resolved = base_dir.resolve()
    destination = (base_dir / relative_path).resolve()
    if base_resolved not in destination.parents:
        msg = f"Invalid runtimeConfig file path outside config directory: '{relative_path}'"
        raise ValueError(msg)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def _materialize_config(runtime_config: dict[str, Any]) -> Path:
    config_dir = Path(tempfile.mkdtemp(prefix="agentcore_nemo_guardrails_"))
    _write_safe_file(config_dir, "config.yml", runtime_config["config_yml"])
    _write_safe_file(config_dir, "rails.co", runtime_config["rails_co"])

    prompts_yml = runtime_config.get("prompts_yml")
    if isinstance(prompts_yml, str) and prompts_yml.strip():
        _write_safe_file(config_dir, "prompts.yml", prompts_yml)

    for relative_path, content in runtime_config.get("files", {}).items():
        if not isinstance(relative_path, str) or not isinstance(content, str):
            msg = "runtimeConfig 'files' entries must be string path -> string content."
            raise ValueError(msg)
        _write_safe_file(config_dir, relative_path, content)

    return config_dir


def _build_rails_from_config_path(config_dir: Path) -> Any:
    try:
        from nemoguardrails import LLMRails, RailsConfig
    except ImportError as exc:
        msg = "nemoguardrails is not installed. Install it before enabling the NeMo guardrail component."
        raise RuntimeError(msg) from exc

    rails_config = RailsConfig.from_path(str(config_dir))
    return LLMRails(rails_config)


def _create_cached_rails(runtime_config: dict[str, Any], cache_key: str) -> _CachedRails:
    config_dir = _materialize_config(runtime_config)
    try:
        rails = _build_rails_from_config_path(config_dir)
    except Exception:  # noqa: BLE001
        shutil.rmtree(config_dir, ignore_errors=True)
        raise
    return _CachedRails(cache_key=cache_key, rails=rails, config_path=config_dir)


def _cleanup_cached_entry(entry: _CachedRails | None) -> None:
    if entry is None:
        return
    shutil.rmtree(entry.config_path, ignore_errors=True)


def _build_cache_key(runtime_config: dict[str, Any], updated_at: datetime | None) -> str:
    updated_at_iso = (updated_at or datetime.now(timezone.utc)).isoformat()
    payload = {"runtime_config": runtime_config, "updated_at": updated_at_iso}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def _get_or_create_rails(
    guardrail_id: UUID,
    runtime_config: dict[str, Any],
    updated_at: datetime | None,
) -> Any:
    cache_key = _build_cache_key(runtime_config, updated_at)
    cache_id = str(guardrail_id)

    with _RAILS_CACHE_LOCK:
        cached = _RAILS_CACHE.get(cache_id)
        if cached and cached.cache_key == cache_key:
            return cached.rails

    new_entry = await asyncio.to_thread(_create_cached_rails, runtime_config, cache_key)

    with _RAILS_CACHE_LOCK:
        cached = _RAILS_CACHE.get(cache_id)
        if cached and cached.cache_key == cache_key:
            _cleanup_cached_entry(new_entry)
            return cached.rails
        old_entry = _RAILS_CACHE.get(cache_id)
        _RAILS_CACHE[cache_id] = new_entry

    _cleanup_cached_entry(old_entry)
    return new_entry.rails


def _extract_generated_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("content", "text", "response", "output"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        return str(result)

    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                chunks.append(chunk)
            elif isinstance(chunk, dict):
                value = chunk.get("text") or chunk.get("content")
                if isinstance(value, str):
                    chunks.append(value)
        if chunks:
            return " ".join(chunks)

    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text

    return str(result)


def _classify_action(input_text: str, output_text: str) -> str:
    if not output_text.strip():
        return "blocked"
    if output_text.strip() == input_text.strip():
        return "passthrough"
    return "rewritten"


async def apply_nemo_guardrail_text(input_text: str, guardrail_id: str) -> GuardrailExecutionResult:
    guardrail_uuid = _to_uuid(guardrail_id)
    guardrail = await _get_guardrail(guardrail_uuid)
    runtime_config = _normalize_runtime_config(guardrail.runtime_config)
    rails = await _get_or_create_rails(
        guardrail_id=guardrail_uuid,
        runtime_config=runtime_config,
        updated_at=guardrail.updated_at,
    )

    messages = [{"role": "user", "content": input_text}]
    generated = rails.generate_async(messages=messages)
    if asyncio.iscoroutine(generated):
        generated = await generated

    output_text = _extract_generated_text(generated)
    action = _classify_action(input_text=input_text, output_text=output_text)
    logger.debug(f"NeMo guardrail applied: guardrail_id={guardrail_id}, action={action}")
    return GuardrailExecutionResult(output_text=output_text, action=action, guardrail_id=guardrail_id)


def clear_nemo_guardrails_cache() -> None:
    with _RAILS_CACHE_LOCK:
        entries = list(_RAILS_CACHE.values())
        _RAILS_CACHE.clear()
    for entry in entries:
        _cleanup_cached_entry(entry)


def invalidate_nemo_guardrail_cache(guardrail_id: str | UUID) -> None:
    cache_id = str(guardrail_id)
    with _RAILS_CACHE_LOCK:
        entry = _RAILS_CACHE.pop(cache_id, None)
    _cleanup_cached_entry(entry)
