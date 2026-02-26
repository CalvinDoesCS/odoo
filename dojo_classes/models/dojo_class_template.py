from odoo import fields, models


class DojoClassTemplate(models.Model):
    _name = "dojo.class.template"
    _description = "Dojo Class Template"

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    level = fields.Selection(
        [
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("all", "All Levels"),
        ],
        default="all",
        required=True,
    )
    duration_minutes = fields.Integer(default=60)
    max_capacity = fields.Integer(default=20)
    instructor_profile_ids = fields.Many2many(
        "dojo.instructor.profile", string="Instructors"
    )
    description = fields.Text()
