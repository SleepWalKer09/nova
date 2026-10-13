import json
import sqlite3
from typing import Any

from app.database import DB_PATH



def create_approval_request(
    ticket_id: int,
) -> dict[str, Any]:
    """Create or reuse a pending request to close a ticket.

    Args:
        ticket_id: ID of the ticket proposed for closure.

    Returns:
        A dictionary with the request or an error message.
    """

    if isinstance(ticket_id, bool) or not isinstance(ticket_id, int):
        return {
            "success": False,
            "error": "Ticket ID must be an integer.",
        }

    connection = None

    try:
        connection = sqlite3.connect(
            DB_PATH,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row

        # Serialize concurrent creation attempts.
        connection.execute("BEGIN IMMEDIATE")

        ticket = connection.execute(
            """
            SELECT id, status
            FROM support_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()

        if ticket is None:
            connection.rollback()
            return {
                "success": False,
                "error": f"Ticket {ticket_id} was not found.",
            }

        if ticket["status"] not in ("open", "in_progress"):
            connection.rollback()
            return {
                "success": False,
                "error": (
                    f"Ticket {ticket_id} cannot be closed "
                    f"because its status is '{ticket['status']}'."
                ),
            }

        # Reuse an existing pending request for this action and ticket.
        existing = connection.execute(
            """
            SELECT
                id,
                action,
                target_ticket_id,
                expected_status,
                status,
                created_at,
                approved_at,
                resolved_at,
                result
            FROM approval_requests
            WHERE action = ?
              AND target_ticket_id = ?
              AND status = 'pending'
            ORDER BY id DESC
            LIMIT 1
            """,
            ("close_support_ticket", ticket_id),
        ).fetchone()

        if existing is not None:
            connection.commit()
            return {
                "success": True,
                "created": False,
                "duplicate": True,
                "request": dict(existing),
            }

        cursor = connection.execute(
            """
            INSERT INTO approval_requests (
                action,
                target_ticket_id,
                expected_status
            )
            VALUES (?, ?, ?)
            """,
            (
                "close_support_ticket",
                ticket_id,
                ticket["status"],
            ),
        )

        request_id = cursor.lastrowid

        request = connection.execute(
            """
            SELECT
                id,
                action,
                target_ticket_id,
                expected_status,
                status,
                created_at,
                approved_at,
                resolved_at,
                result
            FROM approval_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        connection.commit()

        return {
            "success": True,
            "created": True,
            "duplicate": False,
            "request": dict(request),
        }

    except sqlite3.DatabaseError:
        if connection is not None:
            connection.rollback()

        return {
            "success": False,
            "error": "Could not create the approval request.",
        }

    finally:
        if connection is not None:
            connection.close()


def get_approval_request(
    request_id: int,
) -> dict[str, Any]:
    """Retrieve an approval request by ID.

    Args:
        request_id: ID of the request to retrieve.

    Returns:
        A dictionary containing the request or an error message.
    """

    if isinstance(request_id, bool) or not isinstance(request_id, int):
        return {
            "success": False,
            "error": "Request ID must be an integer.",
        }

    connection = None

    try:
        connection = sqlite3.connect(
            DB_PATH,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
                id,
                action,
                target_ticket_id,
                expected_status,
                status,
                created_at,
                approved_at,
                resolved_at,
                result
            FROM approval_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        if row is None:
            return {
                "success": False,
                "error": f"Approval request {request_id} was not found.",
            }

        request = dict(row)

        return {
            "success": True,
            "request": request,
        }

    except sqlite3.DatabaseError:
        return {
            "success": False,
            "error": "Could not retrieve the approval request.",
        }

    finally:
        if connection is not None:
            connection.close()



def approve_request(request_id: int) -> dict[str, Any]:
    """Approve a pending request without executing its action.

    Args:
        request_id: ID of the request to approve.

    Returns:
        A dictionary containing the updated request or an error.
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

        # Serialize competing approval/rejection attempts.
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute(
            """
            UPDATE approval_requests
            SET
                status = 'approved',
                approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'pending'
            """,
            (request_id,),
        )

        if cursor.rowcount != 1:
            connection.rollback()

            return {
                "success": False,
                "error": (
                    "Request not found or no longer pending. "
                    "No changes were made."
                ),
            }

        row = connection.execute(
            """
            SELECT id, action, target_ticket_id, expected_status,
                   status, created_at, approved_at, resolved_at, result
            FROM approval_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        connection.commit()

        return {
            "success": True,
            "request": dict(row),
        }

    except sqlite3.DatabaseError:
        if connection is not None:
            connection.rollback()

        return {
            "success": False,
            "error": "Could not approve the request.",
        }

    finally:
        if connection is not None:
            connection.close()


def reject_request(request_id: int) -> dict[str, Any]:
    """Reject a pending request without executing its action.

    Args:
        request_id: ID of the request to reject.

    Returns:
        A dictionary containing the updated request or an error.
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

        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute(
            """
            UPDATE approval_requests
            SET
                status = 'rejected',
                resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'pending'
            """,
            (request_id,),
        )

        if cursor.rowcount != 1:
            connection.rollback()

            return {
                "success": False,
                "error": (
                    "Request not found or no longer pending. "
                    "No changes were made."
                ),
            }

        row = connection.execute(
            """
            SELECT id, action, target_ticket_id, expected_status,
                   status, created_at, approved_at, resolved_at, result
            FROM approval_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()

        connection.commit()

        return {
            "success": True,
            "request": dict(row),
        }

    except sqlite3.DatabaseError:
        if connection is not None:
            connection.rollback()

        return {
            "success": False,
            "error": "Could not reject the request.",
        }

    finally:
        if connection is not None:
            connection.close()


def list_approval_requests(
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """List recent approval requests with optional filters.

    Args:
        status: Optional approval status to filter by.
        limit: Maximum number of requests to return.

    Returns:
        A dictionary containing the requests or an error message.
    """

    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
        "executed",
        "failed",
    }

    if status is not None and status not in allowed_statuses:
        return {
            "success": False,
            "error": "Invalid approval status.",
        }

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 100
    ):
        return {
            "success": False,
            "error": "Limit must be an integer between 1 and 100.",
        }

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            if status is None:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM approval_requests
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM approval_requests
                    WHERE status = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()

            requests = [dict(row) for row in rows]

        return {
            "success": True,
            "requests": requests,
            "count": len(requests),
        }

    except sqlite3.Error:
        return {
            "success": False,
            "error": "Database error while listing approval requests.",
        }



def get_approval_summary() -> dict:
    """Return request counts grouped by approval status.

    Returns:
        A dictionary containing status counts or an error message.
    """

    statuses = (
        "pending",
        "approved",
        "rejected",
        "executed",
        "failed",
    )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM approval_requests
                GROUP BY status
                """
            ).fetchall()

        counts = {status: 0 for status in statuses}

        for status, total in rows:
            if status in counts:
                counts[status] = total

        counts["total"] = sum(counts.values())

        return {
            "success": True,
            "counts": counts,
        }

    except sqlite3.Error:
        return {
            "success": False,
            "error": "Database error while retrieving approval summary.",
        }
