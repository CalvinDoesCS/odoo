"""Post-install / post-migrate hooks for dojo_subscriptions."""
import logging

from odoo import fields

_logger = logging.getLogger(__name__)


def populate_program_enrollments(env):
    """Create dojo.program.enrollment records for all existing active subscriptions.

    This is safe to run multiple times — it checks for duplicates before
    inserting.  It runs automatically on fresh install (post_init_hook) and
    on module upgrade via the migration script.
    """
    _logger.info("dojo_subscriptions: backfilling program enrollment records …")

    active_subs = env["dojo.member.subscription"].sudo().search([
        ("state", "=", "active"),
        ("program_id", "!=", False),
    ])

    created = 0
    for sub in active_subs:
        existing = env["dojo.program.enrollment"].sudo().search([
            ("member_id", "=", sub.member_id.id),
            ("program_id", "=", sub.program_id.id),
            ("subscription_id", "=", sub.id),
        ], limit=1)
        if not existing:
            env["dojo.program.enrollment"].sudo().create({
                "member_id": sub.member_id.id,
                "program_id": sub.program_id.id,
                "subscription_id": sub.id,
                "is_active": True,
                "enrolled_date": sub.start_date or fields.Date.today(),
                "company_id": sub.company_id.id,
            })
            created += 1

    _logger.info(
        "dojo_subscriptions: created %d program enrollment record(s).", created
    )
