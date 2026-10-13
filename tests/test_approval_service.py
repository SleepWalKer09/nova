import pytest

import app.approval_service as approval_service
import app.database as database
import app.database_tool as database_tool
from app.approval_service import approve_request, reject_request
from app.database_tool import query_database

from app.approval_service import (
    create_approval_request,
    get_approval_request,
)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Initialize a temporary database for each test."""
    test_database_path = tmp_path / "nova-test.db"
    monkeypatch.setattr(database, "DB_PATH", test_database_path)
    monkeypatch.setattr(approval_service, "DB_PATH", test_database_path)
    monkeypatch.setattr(database_tool, "DB_PATH", test_database_path)
    database.init_db()


def test_create_pending_approval_request():
    """Verify valid tickets produce pending close requests."""
    result = create_approval_request(104)

    assert result["success"] is True

    request = result["request"]

    assert request["action"] == "close_support_ticket"
    assert request["target_ticket_id"] == 104
    assert request["expected_status"] == "open"
    assert request["status"] == "pending"


def test_get_existing_approval_request():
    """Verify an existing approval request can be retrieved."""
    created = create_approval_request(101)
    assert created["success"] is True

    request_id = created["request"]["id"]
    result = get_approval_request(request_id)

    assert result["success"] is True
    assert result["request"]["id"] == request_id
    assert result["request"]["status"] == "pending"


def test_reject_nonexistent_ticket():
    """Verify requests cannot be created for unknown tickets."""
    result = create_approval_request(99999)

    assert result["success"] is False


def test_reject_closed_ticket():
    """Verify a closed ticket cannot receive a close request."""
    # Demo ticket 103 is already closed.
    result = create_approval_request(103)

    assert result["success"] is False


def test_reject_invalid_ticket_id():
    """Verify ticket IDs with invalid types are rejected."""
    result = create_approval_request(True)

    assert result["success"] is False


def test_reject_nonexistent_approval_request():
    """Verify unknown approval request IDs return a failure."""
    result = get_approval_request(99999)

    assert result["success"] is False


def test_approve_pending_request():
    """Verify a pending request can be approved without execution."""
    created = create_approval_request(104)
    request_id = created["request"]["id"]

    result = approve_request(request_id)

    assert result["success"] is True
    assert result["request"]["status"] == "approved"
    assert result["request"]["approved_at"] is not None


def test_reject_pending_request():
    """Verify a pending request can be rejected."""
    created = create_approval_request(101)
    request_id = created["request"]["id"]

    result = reject_request(request_id)

    assert result["success"] is True
    assert result["request"]["status"] == "rejected"
    assert result["request"]["resolved_at"] is not None


def test_cannot_approve_request_twice():
    """Verify an already approved request cannot be approved again."""
    created = create_approval_request(104)
    request_id = created["request"]["id"]

    first = approve_request(request_id)
    second = approve_request(request_id)

    assert first["success"] is True
    assert second["success"] is False


def test_cannot_reject_approved_request():
    """Verify an approved request cannot subsequently be rejected."""
    created = create_approval_request(104)
    request_id = created["request"]["id"]

    approved = approve_request(request_id)
    rejected = reject_request(request_id)

    assert approved["success"] is True
    assert rejected["success"] is False


def test_cannot_approve_rejected_request():
    """Verify a rejected request cannot subsequently be approved."""
    created = create_approval_request(101)
    request_id = created["request"]["id"]

    rejected = reject_request(request_id)
    approved = approve_request(request_id)

    assert rejected["success"] is True
    assert approved["success"] is False


def test_approval_does_not_change_ticket():
    """Verify approval alone leaves the ticket unchanged."""
    before = query_database(
        "SELECT id, status FROM support_tickets WHERE id = 104"
    )
    assert before["success"] is True

    created = create_approval_request(104)
    request_id = created["request"]["id"]

    result = approve_request(request_id)
    assert result["success"] is True

    after = query_database(
        "SELECT id, status FROM support_tickets WHERE id = 104"
    )
    assert after["success"] is True
    assert after["rows"] == before["rows"]


def test_duplicate_pending_request_is_not_created():
    """Verify duplicate pending requests reuse the existing request."""
    first = create_approval_request(101)
    second = create_approval_request(101)

    assert first["success"] is True
    assert second["success"] is True

    assert first["created"] is True
    assert first["duplicate"] is False

    assert second["created"] is False
    assert second["duplicate"] is True

    # Both calls must refer to the same approval request.
    assert second["request"]["id"] == first["request"]["id"]
    assert second["request"]["target_ticket_id"] == 101
    assert second["request"]["status"] == "pending"


def test_new_request_allowed_after_previous_request_is_rejected():
    """Verify rejection permits a new request for the same ticket."""
    first = create_approval_request(101)

    assert first["success"] is True
    first_request_id = first["request"]["id"]

    rejected = reject_request(first_request_id)

    assert rejected["success"] is True
    assert rejected["request"]["status"] == "rejected"

    second = create_approval_request(101)

    assert second["success"] is True
    assert second["created"] is True
    assert second["duplicate"] is False
    assert second["request"]["id"] != first_request_id
    assert second["request"]["target_ticket_id"] == 101
    assert second["request"]["status"] == "pending"
