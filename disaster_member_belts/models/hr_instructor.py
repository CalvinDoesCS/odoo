# -*- coding: utf-8 -*-
"""
hr_instructor.py
----------------
Bridges the Dojo Manager instructor system with the Odoo HR module.

hr.employee  ←→  res.partner (work_contact_id)
  │
  └─ is_dojo_instructor
  └─ instructor_belt_rank
  └─ instructor_specializations
  └─ instructor_bio

res.partner (is_instructor=True)
  └─ action_create_employee_profile()   → creates linked hr.employee
  └─ The hr module already provides:
       employee_ids, employees_count, action_open_employees, smart button
"""

from odoo import api, fields, models

BELT_SELECTION = [
    ('white',  'White'),
    ('yellow', 'Yellow'),
    ('orange', 'Orange'),
    ('green',  'Green'),
    ('blue',   'Blue'),
    ('purple', 'Purple'),
    ('brown',  'Brown'),
    ('red',    'Red'),
    ('black',  'Black'),
]


class HrEmployeeInstructor(models.Model):
    _inherit = 'hr.employee'

    is_dojo_instructor = fields.Boolean(
        string='Is Dojo Instructor',
        default=False,
        help='Tick if this employee also serves as a dojo instructor.',
    )
    instructor_belt_rank = fields.Selection(
        selection=BELT_SELECTION,
        string="Instructor's Belt Rank",
    )
    instructor_specializations = fields.Char(
        string='Specializations',
        help='e.g. BJJ, Kids Classes, Competition Prep',
    )
    instructor_bio = fields.Text(
        string='Instructor Bio',
    )
    # Convenience link back to the dojo partner profile
    dojo_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Dojo Member Profile',
        compute='_compute_dojo_partner',
        store=False,
    )

    @api.depends('work_contact_id')
    def _compute_dojo_partner(self):
        for emp in self:
            partner = emp.work_contact_id
            if partner and partner.is_instructor:
                emp.dojo_partner_id = partner
            else:
                emp.dojo_partner_id = False

    def action_open_dojo_profile(self):
        self.ensure_one()
        partner = self.work_contact_id
        if not partner:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': f'Dojo Profile – {self.name}',
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
        }


class ResPartnerInstructor(models.Model):
    _inherit = 'res.partner'

    def action_create_employee_profile(self):
        """
        Create an hr.employee linked to this instructor partner and
        copy over the instructor metadata.  If one already exists,
        open it instead.
        """
        self.ensure_one()
        # If employee already exists, just open it
        if self.employee_ids:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Employee Profile',
                'res_model': 'hr.employee',
                'res_id': self.employee_ids[0].id,
                'view_mode': 'form',
            }
        # Resolve Instructors department
        dept = self.env.ref(
            'disaster_member_belts.hr_dept_instructors', raise_if_not_found=False
        ) or self.env['hr.department'].search([('name', '=', 'Instructors')], limit=1)
        # Create employee linked to this partner
        employee = self.env['hr.employee'].create({
            'name':                     self.name,
            'work_contact_id':          self.id,
            'work_email':               self.email or '',
            'work_phone':               self.phone or '',
            'job_title':                'Dojo Instructor',
            'department_id':            dept.id if dept else False,
            'is_dojo_instructor':       True,
            'instructor_belt_rank':     self.instructor_belt_rank or False,
            'instructor_specializations': self.instructor_specializations or '',
            'instructor_bio':           self.instructor_bio or '',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Employee Profile',
            'res_model': 'hr.employee',
            'res_id': employee.id,
            'view_mode': 'form',
        }
