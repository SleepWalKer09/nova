
import requests
import streamlit as st


API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Nova | Enterprise AI Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Nova")
st.caption("Enterprise AI Agent Platform")
st.divider()


def api_request(method, endpoint, **kwargs):
    """Send a request to the local FastAPI backend.

    Args:
        method: HTTP method to use.
        endpoint: API path relative to the configured base URL.
        **kwargs: Additional arguments passed to ``requests.request``.

    Returns:
        A tuple of the decoded response and an optional error message.
    """
    try:
        response = requests.request(
            method,
            f"{API_BASE_URL}{endpoint}",
            timeout=60,
            **kwargs,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def load_approvals(status):
    """Load approval requests filtered by status.

    Args:
        status: Approval status to request from the API.

    Returns:
        The API response and an optional error message.
    """
    return api_request(
        "GET",
        "/list_approvals",
        params={"status": status, "limit": 100},
    )

def load_approval_summary():
    """Load approval counts from the API.

    Returns:
        The API response and an optional error message.
    """
    return api_request("GET", "/approvals/summary")

def format_action(action: str) -> str:
    """Convert an action identifier to a display label.

    Args:
        action: Internal action identifier.

    Returns:
        Human-readable action label.
    """
    action_labels = {
        "close_support_ticket": "Close support ticket",
    }
    return action_labels.get(action, action.replace("_", " ").title())


def format_status(status: str) -> str:
    """Convert an approval status to a display label.

    Args:
        status: Internal approval status.

    Returns:
        Human-readable approval status.
    """
    status_labels = {
        "pending": "Pending approval",
        "approved": "Approved",
        "rejected": "Rejected",
        "executed": "Executed",
        "failed": "Failed",
    }
    return status_labels.get(status, status.replace("_", " ").title())


def format_ticket_status(status: str) -> str:
    """Convert a ticket status to a display label.

    Args:
        status: Internal ticket status.

    Returns:
        Human-readable ticket status.
    """
    status_labels = {
        "open": "Open",
        "in_progress": "In progress",
    }
    return status_labels.get(status, status.replace("_", " ").title())


def render_summary_metric(label: str, value: int, color: str):
    """Render a labeled metric using the supplied value color.

    Args:
        label: Metric name to display.
        value: Numeric metric value.
        color: CSS color used for the value.
    """

    st.markdown(
        f"""
        <div style="
            background-color: rgba(128, 128, 128, 0.08);
            border-radius: 10px;
            padding: 14px 16px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            min-height: 100px;
        ">
            <div style="
                font-size: 14px;
                color: var(--text-color);
                opacity: 0.8;
            ">{label}</div>
            <div style="
                font-size: 32px;
                font-weight: 600;
                color: {color};
                line-height: 1.4;
            ">{int(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_approval_card(approval):
    """Render an approval request and its available actions.

    Args:
        approval: Request data returned by the API.
    """

    request_id = approval["id"]
    ticket_id = approval["target_ticket_id"]
    request_status = approval["status"]

    action_label = format_action(approval["action"])
    status_label = format_status(request_status)
    expected_status = format_ticket_status(
        approval["expected_status"]
    )

    action_descriptions = {
        "close_support_ticket": (
            "Closes the support ticket after approval "
            "and explicit execution."
        ),
    }
    action_description = action_descriptions.get(
        approval["action"],
        "Performs the requested operation after approval.",
    )

    with st.container(border=True):
        col_info, col_status = st.columns([3, 1])

        with col_info:
            st.markdown(f"**Approval request #{request_id}**")
            st.write(f"**Action:** {action_label}")
            st.caption(action_description)
            st.write(f"**Support ticket:** #{ticket_id}")
            st.write(
                f"**Expected ticket status:** {expected_status}"
            )
            st.caption(f"Created: {approval['created_at']}")

        with col_status:
            st.write("**Status**")
            st.markdown(f"**{status_label}**")

        if request_status == "pending":
            st.warning(
                "⚠️ This operation requires explicit human approval. "
                "The ticket has not been modified."
            )

            col_approve, col_reject = st.columns(2)

            with col_approve:
                if st.button(
                    "Approve",
                    key=f"approve_{request_id}",
                    use_container_width=True,
                ):
                    response, error = api_request(
                        "POST",
                        f"/approvals/{request_id}/approve",
                    )

                    if error:
                        st.error(error)
                    elif response.get("success"):
                        st.success(
                            f"Request #{request_id} approved. "
                            "The ticket has NOT been modified."
                        )
                        st.rerun()
                    else:
                        st.error(response)

            with col_reject:
                if st.button(
                    "Reject",
                    key=f"reject_{request_id}",
                    use_container_width=True,
                ):
                    response, error = api_request(
                        "POST",
                        f"/approvals/{request_id}/reject",
                    )

                    if error:
                        st.error(error)
                    elif response.get("success"):
                        st.success(
                            f"Request #{request_id} rejected."
                        )
                        st.rerun()
                    else:
                        st.error(response)

        elif request_status == "approved":
            st.info(
                "This request is approved but has not been executed. "
                "Execution is a separate operation."
            )

            if st.button(
                "Execute approved action",
                key=f"execute_{request_id}",
            ):
                response, error = api_request(
                    "POST",
                    f"/approvals/{request_id}/execute",
                )

                if error:
                    st.error(error)
                elif response.get("success"):
                    st.success(
                        f"Request #{request_id} executed."
                    )
                    st.json(response)
                    st.rerun()
                else:
                    st.error(response)

        elif request_status == "executed":
            st.success("Action executed successfully.")

        elif request_status == "rejected":
            st.info("This request was rejected.")

        elif request_status == "failed":
            st.error(
                "Execution failed. Review the recorded result."
            )

        if approval.get("result"):
            st.caption("Recorded result")
            st.code(str(approval["result"]))


chat_tab, approvals_tab = st.tabs(
    ["💬 Nova Chat", "🛡️ Approval Center"]
)


# --------------------------------------------------
# CHAT
# --------------------------------------------------

with chat_tab:
    st.subheader("Chat with Nova")
    st.write(
        "Ask questions about customers and support tickets, "
        "or request an action that requires human approval."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_prompt = st.chat_input("Message Nova...")

    if user_prompt:
        st.session_state.messages.append(
            {"role": "user", "content": user_prompt}
        )

        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Nova is thinking..."):
                result, error = api_request(
                    "POST",
                    "/chat",
                    json={"message": user_prompt},
                )

                if error:
                    answer = (
                        "I couldn't connect to the Nova API. "
                        "Check that FastAPI is running."
                    )
                    st.error(error)
                else:
                    answer = result.get(
                        "response",
                        "The API returned no response.",
                    )

                st.markdown(answer)

        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )


# --------------------------------------------------
# APPROVAL CENTER
# --------------------------------------------------

with approvals_tab:
    summary_response, summary_error = load_approval_summary()

    if summary_error:
        st.warning(
            f"Could not load approval summary: {summary_error}"
        )
    elif summary_response.get("success"):
        counts = summary_response["counts"]

        st.subheader("Request Overview")

        col_pending, col_approved, col_executed = st.columns(3)
        col_rejected, col_failed, col_total = st.columns(3)

        with col_pending:
            render_summary_metric(
                "Pending approval",
                counts["pending"],
                "#D97706",
            )

        with col_approved:
            render_summary_metric(
                "Approved",
                counts["approved"],
                "#2563EB",
            )

        with col_executed:
            render_summary_metric(
                "Executed",
                counts["executed"],
                "#16A34A",
            )

        with col_rejected:
            render_summary_metric(
                "Rejected",
                counts["rejected"],
                "#6B7280",
            )

        with col_failed:
            render_summary_metric(
                "Failed",
                counts["failed"],
                "#DC2626",
            )

        with col_total:
            render_summary_metric(
                "Total requests",
                counts["total"],
                "#7C3AED",
            )

        st.divider()

    st.subheader("Human-in-the-Loop Approval Center")
    st.write(
        "Review proposed actions before they can be executed."
    )

    selected_status = st.selectbox(
        "Filter requests",
        options=[
            "pending",
            "approved",
            "rejected",
            "executed",
            "failed",
        ],
        format_func=lambda value: value.capitalize(),
    )

    if st.button("🔄 Refresh requests"):
        st.rerun()

    result, error = load_approvals(selected_status)

    if error:
        st.error(
            "Could not load approval requests. "
            "Verify that FastAPI is running."
        )
        st.caption(error)

    elif result:
        requests_list = result.get("requests", [])

        st.metric(
            f"{selected_status.capitalize()} requests",
            result.get("count", len(requests_list)),
        )

        if not requests_list:
            st.info("No requests found for this status.")

        grouped_approvals = {}
        for approval in requests_list:
            ticket_id = approval["target_ticket_id"]
            grouped_approvals.setdefault(ticket_id, []).append(approval)

        for ticket_id, ticket_approvals in sorted(
            grouped_approvals.items()):
                pending_count = sum(
                    approval["status"] == "pending"
                    for approval in ticket_approvals)

                with st.expander(
                    f"🎫 Ticket #{ticket_id} — "
                    f"{len(ticket_approvals)} request(s) · "
                    f"{pending_count} pending",
                    expanded=(pending_count > 0)):
                    for approval in ticket_approvals:
                        render_approval_card(approval)