from app.hashing import fingerprint
from app.ledger import build_entry, verify_chain
from tests.conftest import make_scene, to_bytes


def chain(n=3):
    entries, prev = [], None
    for seed in range(n):
        prev = build_entry(fingerprint(to_bytes(make_scene(seed))), f"img{seed}", prev)
        entries.append(prev)
    return entries


def test_valid_chain():
    assert verify_chain(chain())["valid"] is True


def test_edited_entry_is_detected():
    entries = chain()
    entries[1]["label"] = "forged"
    result = verify_chain(entries)
    assert result["valid"] is False and result["broken_at"] == 1


def test_deleted_entry_is_detected():
    entries = chain()
    del entries[1]
    assert verify_chain(entries)["valid"] is False


def test_rehashed_forgery_breaks_next_link():
    """Even if an attacker recomputes the edited entry's hash, the next entry exposes it."""
    from app.ledger import _digest

    entries = chain()
    entries[0]["sha256"] = "f" * 64
    entries[0]["entry_hash"] = _digest(entries[0])
    result = verify_chain(entries)
    assert result["valid"] is False and result["broken_at"] == 1
