"""Migration 19.0.4.0.0 → 19.0.4.1.0
Backfill dojo_program_enrollment for all existing active subscriptions.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        INSERT INTO dojo_program_enrollment (
            member_id,
            program_id,
            subscription_id,
            is_active,
            enrolled_date,
            company_id,
            create_uid,
            write_uid,
            create_date,
            write_date
        )
        SELECT
            s.member_id,
            sp.program_id,
            s.id,
            true,
            COALESCE(s.start_date, CURRENT_DATE),
            s.company_id,
            1, 1, NOW(), NOW()
        FROM dojo_member_subscription s
        JOIN dojo_subscription_plan sp ON sp.id = s.plan_id
        WHERE s.state = 'active'
          AND sp.program_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM dojo_program_enrollment e
              WHERE e.member_id = s.member_id
                AND e.program_id = sp.program_id
                AND e.subscription_id = s.id
          )
    """)
    _logger.info(
        "dojo_subscriptions migration 19.0.4.1.0: backfilled %d program enrollment record(s).",
        cr.rowcount,
    )
