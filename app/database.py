import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nova.db"


def init_db() -> None:
    """Create the database schema and insert missing demo records."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                company TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                action TEXT NOT NULL
                    CHECK (action IN ('close_support_ticket')),

                target_ticket_id INTEGER NOT NULL,

                expected_status TEXT NOT NULL
                    CHECK (
                        expected_status IN ('open', 'in_progress')
                    ),

                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        status IN (
                            'pending',
                            'approved',
                            'rejected',
                            'executed',
                            'failed'
                        )
                    ),

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                approved_at TEXT,
                resolved_at TEXT,

                result TEXT,

                FOREIGN KEY (target_ticket_id)
                    REFERENCES support_tickets(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('open', 'in_progress', 'closed')),
                priority TEXT NOT NULL
                    CHECK (priority IN ('low', 'medium', 'high')),
                created_at TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)

        customers = [
            (1, "Ana Torres", "Acme Analytics", "ana@example.com"),
            (2, "Luis García", "Northstar Systems", "luis@example.com"),
            (3, "Sofia Chen", "Acme Analytics", "sofia@example.com"),
            (4, "Daniel Ruiz", "BluePeak Finance", "daniel@example.com"),
        ]

        tickets = [
            (101, 1, "Dashboard not loading", "open", "high", "2026-10-01"),
            (102, 1, "Incorrect monthly report", "in_progress", "medium", "2026-10-03"),
            (103, 2, "Password reset issue", "closed", "low", "2026-10-04"),
            (104, 3, "API integration failing", "open", "high", "2026-10-05"),
            (105, 4, "Export timeout", "open", "medium", "2026-10-06"),
            (106, 2, "Missing account permissions", "in_progress", "high", "2026-10-07"),
        ]

        conn.executemany(
            """
            INSERT OR IGNORE INTO customers
                (id, name, company, email)
            VALUES (?, ?, ?, ?)
            """,
            customers,
        )

        conn.executemany(
            """
            INSERT OR IGNORE INTO support_tickets
                (id, customer_id, title, status, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            tickets,
        )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")
