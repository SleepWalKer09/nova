
import json
import sqlite3
from typing import Any

from app.database import DB_PATH


def execute_approved_request(request_id: int) -> dict[str, Any]:
    """Execute an approved allowlisted action once.

    Args:
        request_id: ID of the approval request to execute.

    Returns:
        A result dictionary describing the execution outcome.
    """

    if isinstance(request_id, bool) or not isinstance(request_id, int):
        return {
            "success": False,
            "error": "Request ID must be an integer.",
        }

    connection = None

    try:
        connection = sqlite3.connect(DB_PATH, timeout=5)
        connection.row_factory = sqlite3.Row

        # Serialize competing operations and start a transaction.
        connection.execute("BEGIN IMMEDIATE")

        request = connection.execute(
            """
            SELECT id, action, target_ticket_id, expected_status, status
            FROM approval_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        if request is None:
            connection.rollback()
            return {
                "success": False,
                "error": f"Approval request {request_id} was not found.",
            }

        if request["status"] != "approved":
            connection.rollback()
            return {
                "success": False,
                "error": "Request is not approved. No action was executed.",
            }

        # Explicit allowlist: never execute arbitrary actions or SQL.
        if request["action"] != "close_support_ticket":
            connection.rollback()
            return {
                "success": False,
                "error": "Action is not allowed.",
            }

        ticket = connection.execute(
            """
            SELECT id, status
            FROM support_tickets
            WHERE id = ?
            """,
            (request["target_ticket_id"],),
        ).fetchone()

        if ticket is None:
            result_message = "Target ticket no longer exists."
            connection.execute(
                """
                UPDATE approval_requests
                SET status = 'failed',
                    resolved_at = CURRENT_TIMESTAMP,
                    result = ?
                WHERE id = ? AND status = 'approved'
                """,
                (result_message, request_id),
            )
            connection.commit()
            return {"success": False, "error": result_message}

        if ticket["status"] != request["expected_status"]:
            result_message = (
                "Ticket status changed after the approval request "
                "was created. No ticket changes were made."
            )
            connection.execute(
                """
                UPDATE approval_requests
                SET status = 'failed',
                    resolved_at = CURRENT_TIMESTAMP,
                    result = ?
                WHERE id = ? AND status = 'approved'
                """,
                (result_message, request_id),
            )
            connection.commit()
            return {"success": False, "error": result_message}

        if ticket["status"] not in ("open", "in_progress"):
            connection.rollback()
            return {
                "success": False,
                "error": "Ticket is not in a closable state.",
            }

        # Conditional update protects against unexpected state changes.
        cursor = connection.execute(
            """
            UPDATE support_tickets
            SET status = 'closed'
            WHERE id = ? AND status = ?
            """,
            (ticket["id"], request["expected_status"]),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return {
                "success": False,
                "error": "Ticket could not be closed safely.",
            }

        result_message = json.dumps(
            {
                "action": request["action"],
                "ticket_id": ticket["id"],
                "previous_status": ticket["status"],
                "new_status": "closed",
            }
        )

        connection.execute(
            """
            UPDATE approval_requests
            SET status = 'executed',
                resolved_at = CURRENT_TIMESTAMP,
                result = ?
            WHERE id = ? AND status = 'approved'
            """,
            (result_message, request_id),
        )

        connection.commit()

        return {
            "success": True,
            "request_id": request_id,
            "ticket_id": ticket["id"],
            "previous_status": ticket["status"],
            "new_status": "closed",
            "status": "executed",
        }

    except sqlite3.DatabaseError:
        if connection is not None:
            connection.rollback()

        return {
            "success": False,
            "error": "Database error. The operation was rolled back.",
        }

    finally:
        if connection is not None:
            connection.close()
