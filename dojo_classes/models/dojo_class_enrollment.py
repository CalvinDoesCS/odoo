from odoo import fields, models


class DojoClassEnrollment(models.Model):
    _name = "dojo.class.enrollment"
    _description = "Dojo Class Enrollment"

    session_id = fields.Many2one(
        "dojo.class.session", required=True, ondelete="cascade", index=True
    )
    member_id = fields.Many2one("dojo.member", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", related="session_id.company_id", store=True, readonly=True
    )
    status = fields.Selection(
        [
            ("registered", "Registered"),
            ("waitlist", "Waitlist"),
            ("cancelled", "Cancelled"),
        ],
        default="registered",
        required=True,
    )
    attendance_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("present", "Present"),
            ("absent", "Absent"),
            ("excused", "Excused"),
        ],
        default="pending",
        required=True,
    )

    _dojo_class_enrollment_unique = models.Constraint(
        "unique(session_id, member_id)",
        "The member is already enrolled in this session.",
    )
