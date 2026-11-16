"""Storage backends: SQLite for local/dev, DynamoDB for AWS.

Both expose the same small interface so the API does not care where data lives.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Protocol

from .config import Settings


class LedgerConflictError(RuntimeError):
    """Another writer appended at the same index; caller should retry."""


class Repository(Protocol):
    def append(self, entry: dict) -> None: ...
    def last(self) -> dict | None: ...
    def get(self, cert_id: str) -> dict | None: ...
    def find_by_sha256(self, sha256: str) -> dict | None: ...
    def all(self) -> list[dict]: ...


class SQLiteRepository:
    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS ledger ("
                " idx INTEGER PRIMARY KEY, cert_id TEXT UNIQUE, sha256 TEXT, body TEXT)"
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS ix_sha ON ledger(sha256)")
            self._conn.commit()

    def append(self, entry: dict) -> None:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO ledger (idx, cert_id, sha256, body) VALUES (?, ?, ?, ?)",
                    (entry["index"], entry["cert_id"], entry["sha256"], json.dumps(entry)),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise LedgerConflictError from exc

    def _one(self, sql: str, args: tuple) -> dict | None:
        with self._lock:
            row = self._conn.execute(sql, args).fetchone()
        return json.loads(row[0]) if row else None

    def last(self) -> dict | None:
        return self._one("SELECT body FROM ledger ORDER BY idx DESC LIMIT 1", ())

    def get(self, cert_id: str) -> dict | None:
        return self._one("SELECT body FROM ledger WHERE cert_id = ?", (cert_id,))

    def find_by_sha256(self, sha256: str) -> dict | None:
        return self._one("SELECT body FROM ledger WHERE sha256 = ? ORDER BY idx LIMIT 1", (sha256,))

    def all(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT body FROM ledger ORDER BY idx").fetchall()
        return [json.loads(r[0]) for r in rows]


class DynamoDBRepository:
    """Single-table design. Partition key ``pk`` = ``SEQ#<index>``.

    The conditional put on ``attribute_not_exists(pk)`` guarantees two
    concurrent writers can never both claim the same ledger index.
    Scans are fine for a demo-sized ledger; a production version would add
    GSIs on cert_id and sha256.
    """

    def __init__(self, table_name: str, region: str):
        import boto3

        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    @staticmethod
    def _from_item(item: dict) -> dict:
        return json.loads(item["body"])

    def append(self, entry: dict) -> None:
        from botocore.exceptions import ClientError

        try:
            self._table.put_item(
                Item={
                    "pk": f"SEQ#{entry['index']:012d}",
                    "cert_id": entry["cert_id"],
                    "sha256": entry["sha256"],
                    "body": json.dumps(entry),
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise LedgerConflictError from exc
            raise

    def _scan(self, **kwargs) -> list[dict]:
        items, start = [], None
        while True:
            if start:
                kwargs["ExclusiveStartKey"] = start
            page = self._table.scan(**kwargs)
            items.extend(page.get("Items", []))
            start = page.get("LastEvaluatedKey")
            if not start:
                return items

    def all(self) -> list[dict]:
        return sorted((self._from_item(i) for i in self._scan()), key=lambda e: e["index"])

    def last(self) -> dict | None:
        entries = self.all()
        return entries[-1] if entries else None

    def _first_where(self, attr: str, value: str) -> dict | None:
        from boto3.dynamodb.conditions import Attr

        matches = [self._from_item(i) for i in self._scan(FilterExpression=Attr(attr).eq(value))]
        return min(matches, key=lambda e: e["index"]) if matches else None

    def get(self, cert_id: str) -> dict | None:
        return self._first_where("cert_id", cert_id)

    def find_by_sha256(self, sha256: str) -> dict | None:
        return self._first_where("sha256", sha256)


def build_repository(settings: Settings) -> Repository:
    if settings.storage_backend == "dynamodb":
        return DynamoDBRepository(settings.dynamodb_table, settings.aws_region)
    return SQLiteRepository(settings.sqlite_path)
