
import sqlite3
import time
from typing import Any

from app.database import DB_PATH

ALLOWED_TABLES = {"customers", "support_tickets"}
MAX_ROWS = 100
MAX_QUERY_SECONDS = 2.0
MAX_VM_STEPS = 500_000


def query_database(sql: str) -> dict[str, Any]:
    """Run one bounded, read-only query against approved tables.

    Args:
        sql: Single SQL query to execute.

    Returns:
        A dictionary containing result rows or an error message.
    """

    if not isinstance(sql, str) or not sql.strip():
        return {"success": False, "error": "Query cannot be empty."}

    connection = None

    try:
        # Read-only mode prevents database modifications.
        connection = sqlite3.connect(
            f"{DB_PATH.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row

        # Additional read-only enforcement within SQLite.
        connection.execute("PRAGMA query_only = ON")

        def authorize(action, arg1, arg2, database_name, trigger_name):
            """Allow only reads from approved database tables."""
            # Permit SELECT statements and reads from approved tables only.
            if action == sqlite3.SQLITE_SELECT:
                return sqlite3.SQLITE_OK

            if action == sqlite3.SQLITE_RECURSIVE:
                return sqlite3.SQLITE_OK

            if action == sqlite3.SQLITE_READ:
                if arg1 in ALLOWED_TABLES:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            # Permit standard SQL functions, but no other operations.
            if action == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_OK

            # Deny writes, schema changes, PRAGMAs, ATTACH, and
            # every operation not explicitly permitted above.
            return sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)

        started_at = time.monotonic()
        vm_steps = 0

        def limit_execution():
            """Interrupt the query when its time or VM-step limit is reached."""
            nonlocal vm_steps
            vm_steps += 1

            elapsed = time.monotonic() - started_at

            if elapsed > MAX_QUERY_SECONDS:
                return 1

            if vm_steps * 1000 > MAX_VM_STEPS:
                return 1

            return 0

        # Called every 1,000 SQLite virtual-machine instructions.
        connection.set_progress_handler(limit_execution, 1000)

        # execute() accepts one statement and rejects multiple statements.
        cursor = connection.execute(sql)

        if cursor.description is None:
            return {
                "success": False,
                "error": "Only read-only queries returning rows are allowed.",
            }

        rows = cursor.fetchmany(MAX_ROWS + 1)

        if len(rows) > MAX_ROWS:
            return {
                "success": False,
                "error": f"Query returned more than {MAX_ROWS} rows.",
            }

        return {
            "success": True,
            "columns": [column[0] for column in cursor.description],
            "rows": [dict(row) for row in rows],
            "row_count": len(rows),
        }

    except sqlite3.DatabaseError as exc:
        message = str(exc)

        if "interrupted" in message.lower():
            message = "Query exceeded its execution limits."

        return {"success": False, "error": message}

    finally:
        if connection is not None:
            connection.close()
