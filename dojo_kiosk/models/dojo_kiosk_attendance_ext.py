"""
Extends dojo.attendance.log with a checkout_datetime field so the kiosk
can record when a member physically leaves.

NOTE: checkout_datetime is now defined on the base dojo.attendance.log model
in dojo_attendance. This file is kept for backwards compatibility but adds
no new fields.
"""
from odoo import models


class DojoAttendanceLogKioskExt(models.Model):
    _inherit = "dojo.attendance.log"
