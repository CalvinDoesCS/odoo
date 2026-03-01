from odoo import fields, models


class DojoMemberRank(models.Model):
    _name = "dojo.member.rank"
    _description = "Dojo Member Rank History"
    _order = "date_awarded desc"

    member_id = fields.Many2one(
        "dojo.member", required=True, ondelete="cascade", index=True
    )
    rank_id = fields.Many2one(
        "dojo.belt.rank", required=True, ondelete="restrict", index=True
    )
    date_awarded = fields.Date(required=True, default=fields.Date.today)
    awarded_by = fields.Many2one("dojo.instructor.profile", string="Awarded By")
    test_registration_id = fields.Many2one(
        "dojo.belt.test.registration",
        string="Test Registration",
        readonly=True,
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        "res.company",
        related="member_id.company_id",
        store=True,
        index=True,
    )
