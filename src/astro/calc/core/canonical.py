"""Canonical serialization and hashing for byte-identical re-runs (CALC-9, design §7.11)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

import rfc8785
from pydantic import BaseModel

FLOAT_DECIMALS = 9


def to_plain(obj: Any) -> Any:
    """Convert models, enums, datetimes, tuples and floats into canonical JSON values."""
    if isinstance(obj, BaseModel):
        return to_plain(obj.model_dump(mode="python"))
    if isinstance(obj, Enum):
        return to_plain(obj.value)
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("non-finite float cannot be canonicalized")
        r = round(obj, FLOAT_DECIMALS)
        return 0.0 if r == 0 else r  # no negative zero
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise ValueError("naive datetime cannot be canonicalized")
        return obj.isoformat()
    if isinstance(obj, Mapping):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(to_plain(v) for v in obj)
    raise TypeError(f"cannot canonicalize {type(obj).__name__}")


def canonical_json(obj: Any) -> bytes:
    """RFC 8785 (JCS) bytes."""
    return rfc8785.dumps(to_plain(obj))


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()
