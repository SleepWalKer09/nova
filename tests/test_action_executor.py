
import json

import pytest

from app.action_executor import execute_approved_request
from app.approval_service import (
    approve_request,
    create_approval_request,
    get_approval_request,
    reject_request,
)
from app.database import DB_PATH


@pytest.fixture
def ticket_104():
    """Restore ticket 104 to its original state after each test."""
    with __import__("sqlite3").connect(DB_PATH) as connection:
        connection.execute(
            "UPDATE support_tickets SET status = 'open' WHERE id = 104"
        )
        connection.commit()

    yield 104

    with __import__("sqlite3").connect(DB_PATH) as connection:
        connection.execute(
            "UPDATE support_tickets SET status = 'open' WHERE id = 104"
        )
        connection.commit()


def test_execute_approved_request_closes_ticket(ticket_104):
    """Verify an approved request closes its ticket and is marked executed."""
    created = create_approval_request(ticket_104)
    request_id = created["request"]["id"]

    approved = approve_request(request_id)
    assert approved["success"] is True

    result = execute_approved_request(request_id)

    assert result["success"] is True
    assert result["new_status"] == "closed"

    request = get_approval_request(request_id)
    assert request["request"]["status"] == "executed"

    with __import__("sqlite3").connect(DB_PATH) as connection:
        status = connection.execute(
            "SELECT status FROM support_tickets WHERE id = ?",
            (ticket_104,),
        ).fetchone()[0]

    assert status == "closed"


def test_cannot_execute_pending_request(ticket_104):
    """Verify a pending request cannot change its ticket."""
    created = create_approval_request(ticket_104)

    result = execute_approved_request(created["request"]["id"])

    assert result["success"] is False

    with __import__("sqlite3").connect(DB_PATH) as connection:
        status = connection.execute(
            "SELECT status FROM support_tickets WHERE id = ?",
            (ticket_104,),
        ).fetchone()[0]

    assert status == "open"


def test_cannot_execute_rejected_request(ticket_104):
    """Verify a rejected request cannot be executed."""
    created = create_approval_request(ticket_104)
    request_id = created["request"]["id"]

    assert reject_request(request_id)["success"] is True

    result = execute_approved_request(request_id)

    assert result["success"] is False


def test_cannot_execute_same_request_twice(ticket_104):
    """Verify an executed request cannot run a second time."""
    created = create_approval_request(ticket_104)
    request_id = created["request"]["id"]

    assert approve_request(request_id)["success"] is True
    assert execute_approved_request(request_id)["success"] is True

    second_result = execute_approved_request(request_id)

    assert second_result["success"] is False


def test_fails_if_ticket_status_changed(ticket_104):
    """Verify execution fails when the ticket status has changed."""
    created = create_approval_request(ticket_104)
    request_id = created["request"]["id"]

    assert approve_request(request_id)["success"] is True

    # Simulate another process changing the ticket after approval.
    with __import__("sqlite3").connect(DB_PATH) as connection:
        connection.execute(
            "UPDATE support_tickets SET status = 'in_progress' WHERE id = ?",
            (ticket_104,),
        )
        connection.commit()

    result = execute_approved_request(request_id)

    assert result["success"] is False

    request = get_approval_request(request_id)
    assert request["request"]["status"] == "failed"

    with __import__("sqlite3").connect(DB_PATH) as connection:
        status = connection.execute(
            "SELECT status FROM support_tickets WHERE id = ?",
            (ticket_104,),
        ).fetchone()[0]

    assert status == "in_progress"


def test_reject_invalid_request_id():
    """Verify execution rejects request IDs with invalid types."""
    assert execute_approved_request(True)["success"] is False
    assert execute_approved_request("1")["success"] is False


def test_reject_nonexistent_request():
    """Verify execution fails when the request does not exist."""
    result = execute_approved_request(999999999)

    assert result["success"] is False
