"""Append-only, hash-chained ledger.

A lightweight version of the blockchain idea from my PhD research
(video blockchain for evidence integrity): each entry stores the hash of the
previous entry, so editing or deleting any past record breaks the chain and
is detected by ``verify_chain``.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from .hashing import Fingerprint

GENESIS = "0" * 64

# Fields covered by the entry hash. Order is fixed by sort_keys in _digest.
HASHED_FIELDS = (
    "index",
    "cert_id",
    "sha256",
    "phash",
    "block_hashes",
    "width",
    "height",
    "format",
    "label",
    "created_at",
    "prev_hash",
)


def _digest(entry: dict) -> str:
    payload = {k: entry[k] for k in HASHED_FIELDS}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_entry(fp: Fingerprint, label: str | None, prev: dict | None) -> dict:
    entry = {
        "index": 0 if prev is None else prev["index"] + 1,
        "cert_id": str(uuid.uuid4()),
        "sha256": fp.sha256,
        "phash": fp.phash,
        "block_hashes": fp.block_hashes,
        "width": fp.width,
        "height": fp.height,
        "format": fp.format,
        "label": label or "",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "prev_hash": GENESIS if prev is None else prev["entry_hash"],
    }
    entry["entry_hash"] = _digest(entry)
    return entry


def verify_chain(entries: list[dict]) -> dict:
    prev_hash = GENESIS
    for expected_index, entry in enumerate(entries):
        if entry["index"] != expected_index:
            return {"valid": False, "length": len(entries), "broken_at": expected_index,
                    "reason": "missing or out-of-order entry"}
        if entry["prev_hash"] != prev_hash:
            return {"valid": False, "length": len(entries), "broken_at": expected_index,
                    "reason": "previous-hash link broken"}
        if _digest(entry) != entry["entry_hash"]:
            return {"valid": False, "length": len(entries), "broken_at": expected_index,
                    "reason": "entry contents modified"}
        prev_hash = entry["entry_hash"]
    return {"valid": True, "length": len(entries), "broken_at": None, "reason": None}
