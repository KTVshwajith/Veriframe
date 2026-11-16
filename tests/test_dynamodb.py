"""DynamoDB backend tested against a mocked AWS (moto) — no real account needed."""

import boto3
import pytest
from moto import mock_aws

from app.hashing import fingerprint
from app.ledger import build_entry, verify_chain
from app.storage import DynamoDBRepository, LedgerConflictError
from tests.conftest import make_scene, to_bytes


@pytest.fixture
def repo(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with mock_aws():
        boto3.client("dynamodb", region_name="ap-southeast-2").create_table(
            TableName="t",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoDBRepository("t", "ap-southeast-2")


def test_append_and_read(repo):
    prev = None
    for seed in range(3):
        prev = build_entry(fingerprint(to_bytes(make_scene(seed))), None, prev)
        repo.append(prev)
    assert repo.last()["index"] == 2
    assert repo.get(prev["cert_id"])["sha256"] == prev["sha256"]
    assert repo.find_by_sha256(prev["sha256"])["cert_id"] == prev["cert_id"]
    assert verify_chain(repo.all())["valid"]


def test_same_index_twice_is_rejected(repo):
    fp = fingerprint(to_bytes(make_scene(1)))
    repo.append(build_entry(fp, None, None))
    with pytest.raises(LedgerConflictError):
        repo.append(build_entry(fp, "racing writer", None))
