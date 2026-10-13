
from app.database_tool import query_database


def check(name, sql, expected_success):
    """Run a named SQL security check and assert its expected outcome."""
    result = query_database(sql)
    passed = result["success"] is expected_success

    print(f"{'PASS' if passed else 'FAIL'}: {name}")
    print(result)

    assert passed, f"Unexpected result for: {name}"


if __name__ == "__main__":
    check(
        "Read customers",
        "SELECT * FROM customers",
        True,
    )

    check(
        "Read open tickets",
        "SELECT id, title FROM support_tickets WHERE status = 'open'",
        True,
    )

    check(
        "Reject DELETE",
        "DELETE FROM support_tickets",
        False,
    )

    check(
        "Reject INSERT",
        """
        INSERT INTO customers (id, name, company, email)
        VALUES (99, 'Test', 'Test Co', 'test@example.com')
        """,
        False,
    )

    check(
        "Reject unapproved table",
        "SELECT * FROM sqlite_master",
        False,
    )

    check(
        "Reject multiple statements",
        "SELECT * FROM customers; DELETE FROM customers",
        False,
    )

    print("All security checks passed.")
