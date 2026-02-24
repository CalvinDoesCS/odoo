/** @odoo-module **/
/**
 * dojo_dashboard.js  –  Main Dojo Dashboard OWL component.
 * Todo + Calendar are separate widgets. Announcements inline.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DojoTodoWidget } from "./dojo_widgets";
import { DojoCalendarWidget } from "./dojo_widgets";

const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
];

export class DojoDashboard extends Component {
    static template = "dojo_dashboard.Main";
    static props = ["*"];
    static components = { DojoTodoWidget, DojoCalendarWidget };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const now = new Date();
        this.state = useState({
            loading: true,
            month_label: `${MONTH_NAMES[now.getMonth()]} ${now.getFullYear()}`,
            data: {},
            announcements: [],
        });

        onWillStart(async () => {
            await Promise.all([this._loadAnalytics(), this._loadAnnouncements()]);
            this.state.loading = false;
        });
    }

    // ── Analytics ─────────────────────────────────────────────────────────
    async _loadAnalytics() {
        try {
            const d = await this.orm.call("res.partner", "get_dojo_analytics", []);
            this.state.data = d || {};
        } catch (e) {
            console.warn("[dojo_dashboard] get_dojo_analytics failed:", e);
            this.state.data = {};
        }
    }

    // ── Announcements ─────────────────────────────────────────────────────
    async _loadAnnouncements() {
        try {
            this.state.announcements = await this.orm.searchRead(
                "disaster.announcement",
                [["active", "=", true]],
                ["id", "name", "summary", "priority", "is_pinned", "date_start"],
                { order: "is_pinned desc, date_start desc", limit: 5 }
            );
        } catch (e) {
            console.warn("[dojo_dashboard] load announcements failed:", e);
            this.state.announcements = [];
        }
    }

    openAnnouncements() {
        this.action.doAction({
            name: _t("Announcements"),
            type: "ir.actions.act_window",
            res_model: "disaster.announcement",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openAnnouncement(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "disaster.announcement",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ── KPI navigation ────────────────────────────────────────────────────
    _go(model, domain, name, views) {
        this.action.doAction({
            name: _t(name),
            type: "ir.actions.act_window",
            res_model: model,
            view_mode: "list,form",
            views: views || [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openActiveMembers() { this._go("res.partner", [["is_member", "=", true], ["member_stage", "=", "active"]], "Active Members"); }
    openTrialMembers() { this._go("res.partner", [["is_member", "=", true], ["member_stage", "=", "trial"]], "Trial Members"); }
    openNewContacts() { this._go("crm.lead", [["create_date", ">=", _monthStart()]], "New Contacts This Month", [[false, "list"], [false, "kanban"], [false, "form"]]); }
    openAttendance(days) { const cut = new Date(); cut.setDate(cut.getDate() - days); this._go("disaster.class.attendance", [["attendance_date", ">=", cut.toISOString().slice(0, 10)]], `Attendance – last ${days} days`); }
    openNewMemberships() { this._go("disaster.member.contract", [["create_date", ">=", _monthStart()]], "New Memberships"); }
    openUpdatedMemberships() { this._go("disaster.member.contract", [["state", "in", ["active", "trial"]], ["write_date", ">=", _monthStart()], ["create_date", "<", _monthStart()]], "Updated Memberships"); }
    openRenewals() { this._go("disaster.member.contract", [["state", "=", "active"], ["date_start", ">=", _monthStart()]], "Renewals This Month"); }
    openTrialAppts() { this._go("crm.lead", [["type", "=", "lead"], ["active", "=", true]], "Intro / Trial Leads", [[false, "list"], [false, "kanban"], [false, "form"]]); }
    openUpdateAppts() { this._go("mail.activity", [["date_deadline", "<=", _today()], ["res_model", "in", ["res.partner", "disaster.member.contract", "crm.lead"]]], "Overdue Activities"); }
    openInvoices() { this._go("account.move", [["move_type", "=", "out_invoice"], ["invoice_date", ">=", _monthStart()], ["state", "=", "posted"]], "Invoices This Month"); }
    openBarcodeLabels() { this._go("res.partner", [["is_member", "=", true], ["member_barcode", "!=", false]], "Member Barcodes"); }
    openKiosk() { this.action.doAction({ type: "ir.actions.client", tag: "dojo_kiosk.KioskApp" }); }
    configurePayments() { this.action.doAction("payment.action_payment_provider"); }
}

function _monthStart() {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function _today() {
    return new Date().toISOString().slice(0, 10);
}

registry.category("actions").add("dojo_dashboard.action", DojoDashboard);
