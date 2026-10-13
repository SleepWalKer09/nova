from app.database_tool import query_database


def test_query_customers():
    """Verify customer records can be queried."""
    result = query_database("SELECT * FROM customers")

    assert result["success"] is True
    assert result["row_count"] == 4


def test_query_open_tickets():
    """Verify open support tickets can be queried."""
    result = query_database(
        "SELECT id, title FROM support_tickets WHERE status = 'open'"
    )

    assert result["success"] is True
    assert result["row_count"] == 3


def test_block_insert():
    """Verify INSERT statements are rejected."""
    result = query_database(
        """
        INSERT INTO customers (id, name, company, email)
        VALUES (99, 'Test', 'Test Co', 'test@example.com')
        """
    )

    assert result["success"] is False


def test_block_update():
    """Verify UPDATE statements are rejected."""
    result = query_database(
        "UPDATE customers SET name = 'Modified' WHERE id = 1"
    )

    assert result["success"] is False


def test_block_drop():
    """Verify schema-dropping statements are rejected."""
    result = query_database("DROP TABLE customers")

    assert result["success"] is False


def test_block_unapproved_table():
    """Verify reads from unapproved tables are rejected."""
    result = query_database("SELECT * FROM sqlite_master")

    assert result["success"] is False


def test_block_multiple_statements():
    """Verify queries containing multiple statements are rejected."""
    result = query_database(
        "SELECT * FROM customers; DELETE FROM customers"
    )

    assert result["success"] is False


def test_database_unchanged_after_write_attempts():
    """Verify rejected write attempts leave database records unchanged."""
    before = query_database(
        "SELECT id, name, email FROM customers ORDER BY id"
    )
    assert before["success"] is True

    for sql in [
        "DELETE FROM customers",
        "UPDATE customers SET name = 'Modified'",
        "DROP TABLE customers",
    ]:
        result = query_database(sql)
        assert result["success"] is False

    after = query_database(
        "SELECT id, name, email FROM customers ORDER BY id"
    )

    assert after["success"] is True
    assert after["rows"] == before["rows"]