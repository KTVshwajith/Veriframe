"""VeriFrame HTTP API."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from prometheus_client import Counter, Histogram, make_asgi_app

from . import __version__
from .config import Settings
from .config import settings as default_settings
from .hashing import InvalidImageError, changed_regions, fingerprint, hamming
from .ledger import build_entry, verify_chain
from .storage import LedgerConflictError, Repository, build_repository

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("veriframe")

REGISTRATIONS = Counter("veriframe_registrations_total", "Images registered")
VERIFICATIONS = Counter("veriframe_verifications_total", "Verification results", ["verdict"])
LATENCY = Histogram("veriframe_request_seconds", "Request latency", ["path"])

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings = default_settings, repo: Repository | None = None) -> FastAPI:
    repo = repo or build_repository(settings)
    app = FastAPI(
        title="VeriFrame",
        version=__version__,
        description="Register images on a hash-chained ledger and detect later tampering.",
    )
    app.mount("/metrics", make_asgi_app())

    @app.middleware("http")
    async def timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            LATENCY.labels(request.url.path).observe(time.perf_counter() - start)
        return response

    async def read_upload(file: UploadFile) -> bytes:
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Image larger than {settings.max_upload_mb} MB")
        if not data:
            raise HTTPException(400, "Empty upload")
        return data

    def fingerprint_or_400(data: bytes):
        try:
            return fingerprint(data)
        except InvalidImageError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "storage": settings.storage_backend}

    @app.post("/api/v1/images/register", status_code=201)
    async def register(file: UploadFile = File(...), label: str | None = Form(None)):
        data = await read_upload(file)
        fp = fingerprint_or_400(data)

        existing = repo.find_by_sha256(fp.sha256)
        if existing:
            return {"status": "already_registered", "certificate": existing}

        for _ in range(3):  # retry if another writer took the same ledger index
            entry = build_entry(fp, label, repo.last())
            try:
                repo.append(entry)
                break
            except LedgerConflictError:
                continue
        else:
            raise HTTPException(409, "Ledger busy, please retry")

        REGISTRATIONS.inc()
        log.info("registered cert_id=%s index=%s", entry["cert_id"], entry["index"])
        return {"status": "registered", "certificate": entry}

    @app.post("/api/v1/images/verify")
    async def verify(file: UploadFile = File(...)):
        data = await read_upload(file)
        fp = fingerprint_or_400(data)

        exact = repo.find_by_sha256(fp.sha256)
        if exact:
            result = {"verdict": "authentic", "detail": "Byte-for-byte identical to the registered original.",
                      "certificate": exact, "changed_regions": []}
        else:
            # Candidate = closest registered image, judged by whole-image pHash and by how
            # many of the 16 regions still match (so a large local edit can't hide the original).
            best, best_distance, best_key = None, None, None
            for entry in repo.all():
                d = hamming(fp.phash, entry["phash"])
                same_blocks = 16 - len(changed_regions(entry["block_hashes"], fp.block_hashes,
                                                       settings.block_threshold))
                if d > settings.match_threshold and same_blocks < 8:
                    continue
                key = (same_blocks, -d)
                if best_key is None or key > best_key:
                    best, best_distance, best_key = entry, d, key

            if best is None:
                result = {"verdict": "unknown", "detail": "No registered image matches this one.",
                          "certificate": None, "changed_regions": []}
            else:
                regions = changed_regions(best["block_hashes"], fp.block_hashes, settings.block_threshold)
                if regions:
                    result = {"verdict": "tampered",
                              "detail": f"Matches a registered image but {len(regions)} of 16 "
                                        "regions differ.",
                              "certificate": best, "changed_regions": regions}
                else:
                    result = {"verdict": "authentic_reencoded",
                              "detail": "Same visual content as the original, but the file was re-saved, "
                                        "compressed or resized.",
                              "certificate": best, "changed_regions": []}
            result["phash_distance"] = None if best is None else best_distance

        VERIFICATIONS.labels(result["verdict"]).inc()
        return result

    @app.get("/api/v1/certificates/{cert_id}")
    def certificate(cert_id: str):
        entry = repo.get(cert_id)
        if not entry:
            raise HTTPException(404, "Certificate not found")
        return entry

    @app.get("/api/v1/ledger/verify")
    def ledger_verify():
        return verify_chain(repo.all())

    return app


app = create_app()
