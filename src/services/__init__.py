"""Services package."""

from .client_service import (
    activate_client,
    create_client,
    get_client_by_email,
    get_client_by_id,
    get_client_by_stripe_id,
    list_clients,
    update_client_status,
    update_client_stripe,
)
from .email_service import (
    Email,
    archive_email,
    check_inbox,
    read_email,
    render_template,
    send_email,
    send_template,
)
from .project_service import (
    IntakeData,
    approve_project,
    create_project,
    create_project_from_intake,
    get_project,
    get_project_with_sessions,
    list_projects,
    reject_project,
    update_project_status,
)
from .session_service import (
    get_monthly_summary,
    get_sessions_for_project,
    get_total_hours,
    log_session,
    parse_session_json,
)
from .update_service import (
    ClientUpdate,
    ProjectUpdate,
    format_update_text,
    get_client_update,
    send_client_update,
    send_monthly_updates,
    send_weekly_updates,
)
from .stripe_service import (
    StripeEvent,
    create_checkout_session,
    get_customer_email,
    get_portal_url,
    get_subscription_status,
    init_stripe,
    parse_webhook_event,
    verify_webhook_signature,
)

__all__ = [
    # Client
    "create_client",
    "get_client_by_email",
    "get_client_by_id",
    "get_client_by_stripe_id",
    "update_client_status",
    "update_client_stripe",
    "list_clients",
    "activate_client",
    # Project
    "IntakeData",
    "create_project",
    "create_project_from_intake",
    "get_project",
    "get_project_with_sessions",
    "update_project_status",
    "approve_project",
    "reject_project",
    "list_projects",
    # Session
    "log_session",
    "get_sessions_for_project",
    "get_total_hours",
    "get_monthly_summary",
    "parse_session_json",
    # Stripe
    "StripeEvent",
    "init_stripe",
    "verify_webhook_signature",
    "parse_webhook_event",
    "get_customer_email",
    "get_portal_url",
    "get_subscription_status",
    "create_checkout_session",
    # Email
    "Email",
    "render_template",
    "send_email",
    "send_template",
    "check_inbox",
    "read_email",
    "archive_email",
    # Updates
    "ClientUpdate",
    "ProjectUpdate",
    "format_update_text",
    "get_client_update",
    "send_client_update",
    "send_weekly_updates",
    "send_monthly_updates",
]
