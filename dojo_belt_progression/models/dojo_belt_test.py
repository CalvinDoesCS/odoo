from odoo import fields, models


class DojoBeltTest(models.Model):
    _name = "dojo.belt.test"
    _description = "Dojo Belt Test Event"
    _order = "test_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, string="Test Name")
    test_date = fields.Date(required=True, default=fields.Date.today)
    location = fields.Char()
    instructor_profile_id = fields.Many2one(
        "dojo.instructor.profile", string="Lead Instructor"
    )
    max_participants = fields.Integer(default=20)
    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="scheduled",
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    registration_ids = fields.One2many(
        "dojo.belt.test.registration", "test_id", string="Registrations"
    )
    notes = fields.Text()

    def action_start(self):
        self.state = "in_progress"

    def action_complete(self):
        self.state = "completed"

    def action_cancel(self):
        self.state = "cancelled"

    def action_award_rank(self):
        """Delegate to registrations — create rank records for all passing members."""
        self.registration_ids.action_award_rank()
