from unittest.mock import patch
from app.agent.agent import run_agent


def test_agent_creates_approval_request():
    """Verify a close request creates a pending approval without execution."""
    with (
        patch(
            "app.agent.agent.generate_response",
            return_value=(
                '{"action": "request_close_ticket", "ticket_id": 101}'
            ),
        ),
        patch(
            "app.agent.agent.create_approval_request",
            return_value={
                "success": True,
                "request": {
                    "id": 999,
                    "target_ticket_id": 101,
                    "expected_status": "open",
                },
            },
        ) as create_request,
    ):
        response = run_agent("Close ticket 101")

    create_request.assert_called_once_with(101)
    assert "999" in response
    assert "pending" in response
    assert "No changes have been made" in response


def test_agent_rejects_invalid_ticket_id():
    """Verify the agent does not submit an invalid ticket ID."""
    with (
        patch(
            "app.agent.agent.generate_response",
            return_value=(
                '{"action": "request_close_ticket", "ticket_id": true}'
            ),
        ),
        patch(
            "app.agent.agent.create_approval_request"
        ) as create_request,
    ):
        response = run_agent("Close a ticket")

    create_request.assert_not_called()
    assert "valid ticket ID" in response


def test_agent_handles_invalid_json():
    """Verify malformed model output produces a safe response."""
    with patch(
        "app.agent.agent.generate_response",
        return_value="This is not JSON",
    ):
        response = run_agent("Hello")

    assert "safely" in response


def test_agent_handles_approval_creation_failure():
    """Verify approval creation failures are reported to the user."""
    with (
        patch(
            "app.agent.agent.generate_response",
            return_value=(
                '{"action": "request_close_ticket", "ticket_id": 999}'
            ),
        ),
        patch(
            "app.agent.agent.create_approval_request",
            return_value={
                "success": False,
                "error": "Ticket 999 was not found.",
            },
        ),
    ):
        response = run_agent("Close ticket 999")

    assert "Could not create an approval request" in response
    assert "was not found" in response
