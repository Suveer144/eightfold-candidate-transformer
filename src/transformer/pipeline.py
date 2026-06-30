from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import yaml

from .sources.crm import CRMSource
from .sources.notes import NotesSource
from .sources.github import GitHubSource
from .schema import RawRecord
from .merger import group_records, merge_group
from .confidence import compute_confidence, is_low_confidence, DEFAULT_LOW_CONFIDENCE_THRESHOLD
from .projector import project

_SOURCE_REGISTRY: dict[str, type] = {
    "crm": CRMSource,
    "notes": NotesSource,
    "github": GitHubSource,
}


def load_config(config_path: str | None) -> dict | None:
    """
    Load a runtime config. No path -> None, meaning "no reshaping, full
    canonical schema as the default output." JSON and YAML both supported
    (YAML's parser also accepts plain JSON, since JSON is a valid YAML subset);
    .json files are read with the stdlib json module for clarity.
    """
    if not config_path:
        return None
    p = Path(config_path)
    with open(p, encoding="utf-8") as f:
        if p.suffix.lower() == ".json":
            return json.load(f)
        return yaml.safe_load(f) or {}


def run_pipeline(
    sources: list[tuple[str, str]],
    config_path: str | None = None,
) -> dict:
    """
    Main entry point.

    sources: list of (source_type, file_path) tuples
    config_path: optional path to a JSON or YAML runtime config

    Returns a dict with keys "candidates", "invalid_candidates", and "meta".
    """
    config = load_config(config_path)

    all_records: list[RawRecord] = []
    sources_used: list[str] = []

    for src_type, src_path in sources:
        src_cls = _SOURCE_REGISTRY.get(src_type.lower())
        if src_cls is None:
            raise ValueError(
                f"Unknown source type: {src_type!r}. Known types: {sorted(_SOURCE_REGISTRY)}"
            )
        records = src_cls().parse(src_path)
        all_records.extend(records)
        if src_type not in sources_used:
            sources_used.append(src_type)

    groups = group_records(all_records)

    candidates = []
    invalid_candidates = []
    low_conf_count = 0
    threshold = float((config or {}).get("confidence_threshold", DEFAULT_LOW_CONFIDENCE_THRESHOLD))

    for group in groups:
        profile = merge_group(group)
        profile.overall_confidence = compute_confidence(profile)

        if is_low_confidence(profile.overall_confidence, threshold):
            low_conf_count += 1
            profile.warnings.append(
                f"Low confidence: {profile.overall_confidence:.4f} (threshold {threshold:.2f})"
            )

        projected, errors = project(profile, config)
        if projected is None:
            continue  # filtered out by confidence_threshold + include_low_confidence=false
        if errors:
            invalid_candidates.append({
                "candidate_id": profile.candidate_id,
                "errors": errors,
                "partial_record": projected,
            })
        else:
            candidates.append(projected)

    return {
        "candidates": candidates,
        "invalid_candidates": invalid_candidates,
        "meta": {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "sources_used": sources_used,
            "total_candidates": len(candidates),
            "invalid_candidate_count": len(invalid_candidates),
            "low_confidence_count": low_conf_count,
        },
    }
