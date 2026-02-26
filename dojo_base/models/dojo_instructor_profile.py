from odoo import fields, models


class DojoInstructorProfile(models.Model):
    _name = "dojo.instructor.profile"
    _description = "Dojo Instructor Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one("res.users", required=True, tracking=True)
    employee_id = fields.Many2one("hr.employee", tracking=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    bio = fields.Text()

    _dojo_instructor_user_unique = models.Constraint(
        "unique(user_id)",
        "A user can only have one instructor profile.",
    )
