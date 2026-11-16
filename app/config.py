"""Runtime configuration, read from environment variables (12-factor style)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    storage_backend: str = os.getenv("STORAGE_BACKEND", "sqlite")  # sqlite | dynamodb
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/veriframe.db")
    dynamodb_table: str = os.getenv("DYNAMODB_TABLE", "veriframe-ledger")
    aws_region: str = os.getenv("AWS_REGION", "ap-southeast-2")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    # Max perceptual-hash distance (0-64) for two images to count as "the same picture".
    match_threshold: int = int(os.getenv("MATCH_THRESHOLD", "12"))
    # Max per-block hash distance before a region is flagged as modified.
    block_threshold: int = int(os.getenv("BLOCK_THRESHOLD", "8"))


settings = Settings()
