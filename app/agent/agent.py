
import json

from app.agent.ollama_service import generate_response
from app.database_tool import query_database
from app.approval_service import create_approval_request


def run_agent(message: str) -> str:
    """Process a message using read-only queries and gated actions.

    Args:
        message: User message to interpret.

    Returns:
        Agent response or a safe error message.
    """

    decision_prompt = f"""
You are Nova, an enterprise AI assistant.

Available database tables:

customers:
- id, name, company, email

support_tickets:
- id, customer_id, title, status, priority, created_at

Available actions:

1. Answer a general question:
{{"action": "answer", "response": "Your answer"}}

2. Query database records:
{{"action": "query", "sql": "A single SELECT query"}}

3. Propose closing a support ticket:
{{"action": "request_close_ticket", "ticket_id": 101}}

Rules:
- Use "query" for questions requiring actual database records.
- Use "answer" for general questions.
- Use "request_close_ticket" only when the user explicitly
  asks to close a specific support ticket.
- For a close request, provide the ticket ID as an integer.
- Requesting closure only creates an approval request.
- Never claim an action was approved or executed unless
  the system explicitly confirms that result.
- Never generate SQL to modify database records.
- Only request SELECT queries.
- Never invent database results.
- Return JSON only, without Markdown fences.

SQL generation rules:
- If the user asks for a count AND a list of records, return
  individual records so Python can calculate the count.
- Do not combine COUNT(*) with ordinary columns unless using
  a valid GROUP BY and grouped counts are explicitly requested.
- Use only the listed tables and columns.
- If the user asks for ticket titles, include the title column.

User message:
{message}
"""

    raw_decision = generate_response(decision_prompt)

    try:
        decision = json.loads(raw_decision)
    except (json.JSONDecodeError, TypeError):
        return "I couldn't interpret the model's decision safely."

    if not isinstance(decision, dict):
        return "The model returned an invalid decision structure."

    action = decision.get("action")

    if action == "answer":
        response = decision.get("response")
        if isinstance(response, str) and response.strip():
            return response
        return "I couldn't generate a valid response."

    if action == "request_close_ticket":
        ticket_id = decision.get("ticket_id")

        if (
            isinstance(ticket_id, bool)
            or not isinstance(ticket_id, int)
            or ticket_id <= 0
        ):
            return "The model did not provide a valid ticket ID."

        result = create_approval_request(ticket_id)

        if not result.get("success"):
            error = result.get("error", "Unknown approval error.")
            return f"Could not create an approval request: {error}"

        request = result["request"]

        if result.get("duplicate"):
            return (
                f"An existing pending approval request "
                f"#{request['id']} already exists for support "
                f"ticket #{request['target_ticket_id']}. "
                f"Current expected status: "
                f"{request['expected_status']}. "
                "Status: pending. No changes have been made "
                "to the ticket. "
                f"Review the existing request using "
                f"/approvals/{request['id']}."
            )

        return (
            f"Approval request #{request['id']} created for "
            f"support ticket #{request['target_ticket_id']}. "
            f"Current expected status: {request['expected_status']}. "
            "Status: pending. No changes have been made to the ticket. "
            f"Review and approve or reject this request using "
            f"/approvals/{request['id']}."
        )

    if action != "query":
        return "Unsupported action. No database operation was executed."

    sql = decision.get("sql")

    if not isinstance(sql, str) or not sql.strip():
        return "The model did not provide a valid SQL query."

    result = query_database(sql)

    if not result.get("success"):
        error = result.get("error", "Unknown database error.")
        return f"Database query rejected: {error}"

    columns = result["columns"]
    rows = result["rows"]

    if not rows:
        return "No matching records were found."

    output_lines = [
        f"Query returned {result['row_count']} record(s).",
        "",
    ]

    for index, row in enumerate(rows, start=1):
        output_lines.append(
            f"{index}. "
            + " | ".join(
                f"{column}: {row.get(column)}"
                for column in columns
            )
        )

    return "\n".join(output_lines)
