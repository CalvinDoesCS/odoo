from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class DojoOnboardingWizard(models.TransientModel):
    _name = 'dojo.onboarding.wizard'
    _description = 'Member Onboarding Wizard'

    # ── Step navigation ──────────────────────────────────────────────────────
    step = fields.Selection(
        selection=[
            ('member_info',    '1. Member Info'),
            ('household',      '2. Household'),
            ('guardian_setup', '3. Guardian Setup'),
            ('enrollment',     '4. Class Enrollment'),
            ('subscription',   '5. Subscription'),
            ('portal_access',  '6. Portal Access'),
        ],
        default='member_info',
        required=True,
    )

    # ── Step 1: Member Info ───────────────────────────────────────────────────
    name = fields.Char('Full Name', required=True)
    email = fields.Char('Email')
    phone = fields.Char('Phone')
    date_of_birth = fields.Date('Date of Birth')
    role = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('parent', 'Parent'),
            ('both', 'Parent & Student'),
        ],
        default='student',
        required=True,
        string='Role',
    )
    emergency_note = fields.Text('Emergency / Medical Notes')

    # ── Step 2: Household ────────────────────────────────────────────────────
    household_id = fields.Many2one(
        'dojo.household',
        string='Existing Household',
    )
    create_new_household = fields.Boolean('Create a New Household', default=False)

    # New household: guardian member to create first
    new_guardian_name = fields.Char('Guardian Full Name')
    new_guardian_email = fields.Char('Guardian Email')
    new_guardian_phone = fields.Char('Guardian Phone')
    new_guardian_role = fields.Selection(
        selection=[
            ('parent', 'Parent'),
            ('both', 'Parent & Student'),
        ],
        default='parent',
        string='Guardian Role',
    )
    new_household_name = fields.Char(
        'New Household Name',
        help="Leave blank to auto-generate from the guardian's name.",
    )

    guardian_member_id = fields.Many2one(
        'dojo.member',
        string='Guardian Member',
        help='Select an existing member to link as guardian (for students).',
    )
    guardian_relation = fields.Selection(
        selection=[
            ('mother', 'Mother'),
            ('father', 'Father'),
            ('guardian', 'Guardian'),
            ('other', 'Other'),
        ],
        string="Guardian's Relation to New Member",
    )

    # ── Step 3: Class Enrollment ─────────────────────────────────────────────
    session_ids = fields.Many2many(
        'dojo.class.session',
        string='Enroll In Sessions',
        domain="[('state', '=', 'open')]",
    )

    # ── Step 4: Subscription ─────────────────────────────────────────────────
    plan_id = fields.Many2one('dojo.subscription.plan', string='Subscription Plan')
    subscription_start_date = fields.Date(
        'Subscription Start Date',
        default=fields.Date.today,
    )
    # ── Step 5: Portal Access ────────────────────────────────────────────────
    create_portal_login = fields.Boolean(
        'Create Portal Login',
        default=True,
        help='Creates a res.users record linked to the new member so they can log into the portal.',
    )
    send_welcome_email = fields.Boolean(
        'Send Welcome / Password-Reset Email',
        default=True,
    )

    # ── Result (set after confirm) ────────────────────────────────────────────
    created_member_id = fields.Many2one('dojo.member', string='Created Member', readonly=True)

    # ── Step helpers ─────────────────────────────────────────────────────────
    _STEP_ORDER = ['member_info', 'household', 'guardian_setup', 'enrollment', 'subscription', 'portal_access']

    def _reopen_wizard(self):
        """Return an action that re-opens this transient record (keeps state)."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_next(self):
        self.ensure_one()

        # ── Step-specific validation ───────────────────────────────────────
        if self.step == 'member_info':
            if not self.phone:
                raise UserError(_(
                    'A phone number is required for the member.'
                ))
        elif self.step == 'household':
            if not self.create_new_household:
                if not self.household_id:
                    raise UserError(_(
                        'Please select an existing household or choose to create a new one.'
                    ))
        elif self.step == 'guardian_setup':
            if not self.new_guardian_name:
                raise UserError(_(
                    'Guardian full name is required to create a new household.'
                ))
            if not self.new_guardian_phone:
                raise UserError(_(
                    'A phone number is required for the guardian.'
                ))
            if not self.guardian_relation:
                raise UserError(_(
                    "Please specify the guardian's relation to the new member."
                ))

        # ── Advance step, skipping guardian_setup when not creating a new household ──
        idx = self._STEP_ORDER.index(self.step)
        next_step = self._STEP_ORDER[idx + 1] if idx < len(self._STEP_ORDER) - 1 else self.step
        if next_step == 'guardian_setup' and not self.create_new_household:
            next_step = 'enrollment'
        self.step = next_step
        return self._reopen_wizard()

    def action_back(self):
        self.ensure_one()
        idx = self._STEP_ORDER.index(self.step)
        prev_step = self._STEP_ORDER[idx - 1] if idx > 0 else self.step
        # Skip guardian_setup when going back if we're not on the new-household path
        if prev_step == 'guardian_setup' and not self.create_new_household:
            prev_step = 'household'
        self.step = prev_step
        return self._reopen_wizard()

    def action_confirm(self):
        self.ensure_one()

        if not self.name:
            raise UserError(_('Member name is required.'))

        # ── Resolve / create household ────────────────────────────────────────
        household = self.household_id
        guardian_member = None

        if self.create_new_household:
            # Step 1: create the guardian member
            guardian_vals = {
                'name': self.new_guardian_name,
                'email': self.new_guardian_email or False,
                'phone': self.new_guardian_phone or False,
                'role': self.new_guardian_role or 'parent',
                'company_id': self.env.company.id,
            }
            guardian_member = self.env['dojo.member'].create(guardian_vals)

            # Step 2: create household
            hh_name = self.new_household_name or (self.new_guardian_name + ' Household')
            household = self.env['dojo.household'].create({
                'name': hh_name,
                'primary_guardian_id': guardian_member.id,
                'company_id': self.env.company.id,
            })

            # Step 3: assign the guardian to their own household
            guardian_member.write({'household_id': household.id})

        # ── Create new member ─────────────────────────────────────────────────
        member_vals = {
            'name': self.name,
            'email': self.email or False,
            'phone': self.phone or False,
            'date_of_birth': self.date_of_birth or False,
            'role': self.role,
            'emergency_note': self.emergency_note or False,
            'company_id': self.env.company.id,
        }
        if household:
            member_vals['household_id'] = household.id

        member = self.env['dojo.member'].create(member_vals)

        # ── Set primary guardian on household (existing household path) ─────────
        if household and not household.primary_guardian_id:
            if self.role in ('parent', 'both'):
                household.primary_guardian_id = member.id

        # ── Guardian link ─────────────────────────────────────────────────────
        if self.create_new_household and guardian_member and household:
            # New household: newly created guardian → new member
            self.env['dojo.guardian.link'].create({
                'household_id': household.id,
                'guardian_member_id': guardian_member.id,
                'student_member_id': member.id,
                'relation': self.guardian_relation,
                'is_primary': True,
            })
        elif self.guardian_member_id and self.guardian_relation and household:
            # Existing household: selected guardian → new member
            self.env['dojo.guardian.link'].create({
                'household_id': household.id,
                'guardian_member_id': self.guardian_member_id.id,
                'student_member_id': member.id,
                'relation': self.guardian_relation,
                'is_primary': True,
            })

        # ── Class enrollments ─────────────────────────────────────────────────
        for session in self.session_ids:
            # Enforce capacity before enrolling
            if session.seats_taken >= session.capacity:
                raise UserError(_(
                    'Session "%s" is at full capacity (%s/%s). '
                    'Remove it from the enrollment list or increase its capacity.',
                    session.name, session.seats_taken, session.capacity,
                ))
            self.env['dojo.class.enrollment'].create({
                'session_id': session.id,
                'member_id': member.id,
                'status': 'registered',
                'attendance_state': 'pending',
            })

        # ── Subscription ──────────────────────────────────────────────────────
        if self.plan_id:
            sub_start = self.subscription_start_date or fields.Date.today()
            period = self.plan_id.billing_period
            if period == 'weekly':
                next_billing = sub_start + relativedelta(weeks=1)
            elif period == 'yearly':
                next_billing = sub_start + relativedelta(years=1)
            else:
                next_billing = sub_start + relativedelta(months=1)
            self.env['dojo.member.subscription'].create({
                'member_id': member.id,
                'plan_id': self.plan_id.id,
                'start_date': sub_start,
                'next_billing_date': next_billing,
                'state': 'active',
                'company_id': self.env.company.id,
            })

        # ── Issue Stripe card for new households ──────────────────────────────
        if self.create_new_household and household:
            try:
                household.action_create_stripe_cardholder()
                household.action_create_stripe_card()
            except Exception:
                pass  # Stripe not configured yet — admin can issue the card manually from the household form

        # ── Portal login ──────────────────────────────────────────────────────
        if self.create_portal_login:
            if not member.email:
                raise UserError(_(
                    'An email address is required to create a portal login. '
                    'Please add an email in Step 1.'
                ))
            portal_group = self.env.ref('base.group_portal')
            user = self.env['res.users'].create({
                'name': member.name,
                'login': member.email,
                'partner_id': member.partner_id.id,
                'groups_id': [(4, portal_group.id)],
            })
            if self.send_welcome_email:
                user.action_reset_password()

        # ── Onboarding record ──────────────────────────────────────────────────
        self.env['dojo.onboarding.record'].create({
            'member_id': member.id,
            'step_member_info': True,
            'step_household': bool(household),
            'step_enrollment': bool(self.session_ids),
            'step_subscription': bool(self.plan_id),
            'step_portal_access': self.create_portal_login,
            'state': 'completed',
            'company_id': self.env.company.id,
        })

        # Open the newly created member form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dojo.member',
            'res_id': member.id,
            'view_mode': 'form',
            'target': 'current',
        }
