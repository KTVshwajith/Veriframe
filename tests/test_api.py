from PIL import ImageDraw

from tests.conftest import make_scene, to_bytes


def upload(client, path, data, name="img.png", **form):
    return client.post(path, files={"file": (name, data, "application/octet-stream")}, data=form)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_then_exact_match(client, original):
    data = to_bytes(original)
    r = upload(client, "/api/v1/images/register", data, label="site photo")
    assert r.status_code == 201
    cert = r.json()["certificate"]
    assert cert["index"] == 0 and cert["label"] == "site photo"

    v = upload(client, "/api/v1/images/verify", data).json()
    assert v["verdict"] == "authentic"
    assert v["certificate"]["cert_id"] == cert["cert_id"]


def test_duplicate_registration_is_idempotent(client, original):
    data = to_bytes(original)
    first = upload(client, "/api/v1/images/register", data).json()
    second = upload(client, "/api/v1/images/register", data).json()
    assert second["status"] == "already_registered"
    assert second["certificate"]["cert_id"] == first["certificate"]["cert_id"]


def test_reencoded_copy_is_still_recognised(client, original):
    upload(client, "/api/v1/images/register", to_bytes(original))
    jpeg = to_bytes(original.resize((480, 360)), "JPEG", quality=80)
    v = upload(client, "/api/v1/images/verify", jpeg, name="copy.jpg").json()
    assert v["verdict"] == "authentic_reencoded", v


def test_local_edit_is_flagged_and_located(client, original):
    upload(client, "/api/v1/images/register", to_bytes(original))
    edited = original.copy()
    ImageDraw.Draw(edited).rectangle((20, 20, 140, 100), fill=(255, 255, 255))  # top-left
    v = upload(client, "/api/v1/images/verify", to_bytes(edited)).json()
    assert v["verdict"] == "tampered", v
    assert {"row": 0, "col": 0} in [{"row": r["row"], "col": r["col"]} for r in v["changed_regions"]]
    assert len(v["changed_regions"]) < 16


def test_large_edit_still_traced_to_original(client, original):
    upload(client, "/api/v1/images/register", to_bytes(original))
    edited = original.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 320, 240), fill=(0, 0, 0))  # whole top-left quarter
    v = upload(client, "/api/v1/images/verify", to_bytes(edited)).json()
    assert v["verdict"] == "tampered", v
    assert len(v["changed_regions"]) >= 4


def test_unrelated_image_is_unknown(client, original):
    upload(client, "/api/v1/images/register", to_bytes(original))
    v = upload(client, "/api/v1/images/verify", to_bytes(make_scene(99))).json()
    assert v["verdict"] == "unknown"


def test_rejects_non_image(client):
    r = upload(client, "/api/v1/images/register", b"definitely not an image")
    assert r.status_code == 400


def test_certificate_lookup(client, original):
    cert = upload(client, "/api/v1/images/register", to_bytes(original)).json()["certificate"]
    assert client.get(f"/api/v1/certificates/{cert['cert_id']}").json()["sha256"] == cert["sha256"]
    assert client.get("/api/v1/certificates/nope").status_code == 404


def test_ledger_chain_valid_after_several_registrations(client):
    for seed in range(4):
        upload(client, "/api/v1/images/register", to_bytes(make_scene(seed + 10)))
    result = client.get("/api/v1/ledger/verify").json()
    assert result == {"valid": True, "length": 4, "broken_at": None, "reason": None}


def test_metrics_exposed(client):
    assert "veriframe_registrations_total" in client.get("/metrics/").text
