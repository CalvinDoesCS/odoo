"""Pre-migration for dojo_classes 19.0.1.2.0

Changes the FK constraint on dojo_class_enrollment.member_id from
ON DELETE RESTRICT → ON DELETE CASCADE so that deleting a dojo.member
automatically removes all their class enrollments.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE dojo_class_enrollment
            DROP CONSTRAINT IF EXISTS dojo_class_enrollment_member_id_fkey;
    """)
    cr.execute("""
        ALTER TABLE dojo_class_enrollment
            ADD CONSTRAINT dojo_class_enrollment_member_id_fkey
            FOREIGN KEY (member_id)
            REFERENCES dojo_member(id)
            ON DELETE CASCADE;
    """)
    _logger.info("dojo_class_enrollment.member_id FK changed to ON DELETE CASCADE")
