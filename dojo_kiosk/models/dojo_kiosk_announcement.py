from odoo import fields, models


class DojoKioskAnnouncement(models.Model):
    _name = "dojo.kiosk.announcement"
    _description = "Kiosk Idle Screen Announcement"
    _order = "sequence, id"

    config_id = fields.Many2one(
        "dojo.kiosk.config",
        required=True,
        ondelete="cascade",
        index=True,
    )
    title = fields.Char(required=True)
    body = fields.Text(help="Shown under the title on the idle screen.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
