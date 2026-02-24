/** @odoo-module **/
/**
 * dojo_kiosk/static/src/js/kiosk_app.js
 * ----------------------------------------
 * Dojo Kiosk — Roster-based kiosk with Instructor Mode.
 *
 * Main screen: scrollable session roster blocks with member avatar grid.
 * Instructor mode (PIN-gated): check-in/out, add/remove from roster.
 * Student mode: confirm popup → check-in.
 */

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const BARCODE_DEBOUNCE_MS = 60;
const SEARCH_DEBOUNCE_MS = 400;
const TOAST_DURATION_MS = 3500;
const IDLE_RESET_MS = 120_000;   // 2 min idle → exit instructor mode

export class KioskApp extends Component {
    static template = "dojo_kiosk.KioskApp";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            // roster data
            sessions: [],
            loading: false,
            sessionFilter: "all",   // "all" | session_id
            searchQuery: "",

            // instructor mode
            instructorMode: false,
            showPinModal: false,
            staffPin: "",
            pinError: "",

            // search overlay (global member search)
            showSearchOverlay: false,
            searchLoading: false,
            globalSearchResults: [],

            // member detail popup (instructor)
            showMemberPopup: false,
            memberDetail: null,
            loadingMember: false,
            popupSessionId: null,

            // check-in popup (student)
            showCheckinPopup: false,
            checkinMember: null,
            checkinSessionId: null,
            checkinSessionName: "",

            // toasts
            showSuccessToast: false,
            showErrorToast: false,
            toastMessage: "",
        });

        // Barcode scanner accumulator
        this._barcodeBuffer = "";
        this._barcodeTimer = null;

        // Search debounce
        this._searchTimer = null;

        // Idle timer (auto-disable instructor mode)
        this._idleTimer = null;

        // Bind handlers referenced by OWL arrow functions
        this.openMember = this.openMember.bind(this);
        this.pinPress = this.pinPress.bind(this);
        this.addToRoster = this.addToRoster.bind(this);
        this.removeFromRoster = this.removeFromRoster.bind(this);
        this.doCheckin = this.doCheckin.bind(this);
        this.doCheckout = this.doCheckout.bind(this);
        this.confirmCheckin = this.confirmCheckin.bind(this);
        this.openMemberFromSearch = this.openMemberFromSearch.bind(this);
        this.isMemberInPopupSession = this.isMemberInPopupSession.bind(this);

        onMounted(() => {
            this._init();
            // Route barcode keystrokes to our handler
            this._kbHandler = (ev) => this._onKeydown(ev);
            document.addEventListener("keydown", this._kbHandler);
            // Focus the hidden barcode field to capture scanner input
            const bcEl = document.getElementById("dk-barcode-input");
            if (bcEl) bcEl.focus();
        });

        onWillUnmount(() => {
            document.removeEventListener("keydown", this._kbHandler);
            clearTimeout(this._barcodeTimer);
            clearTimeout(this._searchTimer);
            clearTimeout(this._idleTimer);
        });
    }

    // ─── Init ────────────────────────────────────────────────────

    async _init() {
        await this._loadRoster();
    }

    async _loadRoster() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "dojo.kiosk.config", "kiosk_get_roster_data", []
            );
            this.state.sessions = data;
        } catch (e) {
            this._showError("Failed to load roster: " + (e.message || e));
        } finally {
            this.state.loading = false;
        }
    }

    // ─── Computed ────────────────────────────────────────────────

    get filteredSessions() {
        const { sessions, sessionFilter, searchQuery } = this.state;
        let filtered = sessions;

        if (sessionFilter !== "all") {
            const sid = parseInt(sessionFilter, 10);
            filtered = filtered.filter(s => s.id === sid);
        }

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered
                .map(s => ({
                    ...s,
                    members: s.members.filter(m => m.name.toLowerCase().includes(q))
                }))
                .filter(s => s.members.length > 0);
        }

        return filtered;
    }

    isMemberInPopupSession() {
        const { memberDetail, popupSessionId } = this.state;
        if (!memberDetail || !popupSessionId) return false;
        return memberDetail.today_sessions.some(
            ts => ts.session_id === popupSessionId
        );
    }

    // ─── Activity / idle ─────────────────────────────────────────

    onActivity() {
        this._resetIdleTimer();
    }

    _resetIdleTimer() {
        clearTimeout(this._idleTimer);
        if (this.state.instructorMode) {
            this._idleTimer = setTimeout(() => {
                this._disableInstructor();
            }, IDLE_RESET_MS);
        }
    }

    _disableInstructor() {
        this.state.instructorMode = false;
        this._showSuccess("Instructor mode disabled due to inactivity.");
    }

    // ─── Instructor mode toggle / PIN ─────────────────────────────

    toggleInstructorMode() {
        if (this.state.instructorMode) {
            this._disableInstructor();
        } else {
            this.state.staffPin = "";
            this.state.pinError = "";
            this.state.showPinModal = true;
        }
    }

    closePinModal() {
        this.state.showPinModal = false;
        this.state.staffPin = "";
        this.state.pinError = "";
    }

    pinPress(d) {
        if (d === "⌫") {
            this.state.staffPin = this.state.staffPin.slice(0, -1);
            this.state.pinError = "";
        } else if (this.state.staffPin.length < 6) {
            this.state.staffPin += d;
            if (this.state.staffPin.length === 4) {
                this._submitPin();
            }
        }
    }

    async _submitPin() {
        const pin = this.state.staffPin;
        this.state.loading = true;
        try {
            const ok = await this.orm.call(
                "dojo.kiosk.config", "kiosk_verify_staff_pin", [pin]
            );
            if (ok) {
                this.state.instructorMode = true;
                this.state.showPinModal = false;
                this.state.staffPin = "";
                this.state.pinError = "";
                this._resetIdleTimer();
                this._showSuccess("Instructor mode enabled.");
            } else {
                this.state.pinError = "Incorrect PIN. Try again.";
                this.state.staffPin = "";
            }
        } catch (e) {
            this.state.pinError = "Error verifying PIN.";
            this.state.staffPin = "";
        } finally {
            this.state.loading = false;
        }
    }

    // ─── Roster refresh / filter / search ────────────────────────

    async refreshRoster() {
        await this._loadRoster();
    }

    onSessionFilterChange(ev) {
        this.state.sessionFilter = ev.target.value;
    }

    onSearchInput(ev) {
        const q = ev.target.value.trim();
        this.state.searchQuery = q;

        clearTimeout(this._searchTimer);

        if (!q) {
            this.state.showSearchOverlay = false;
            return;
        }

        // Check if query matches anyone in current roster — if not, show global
        const inRoster = this.filteredSessions.some(s => s.members.length > 0);
        if (!inRoster) {
            this._searchTimer = setTimeout(() => this._globalSearch(q), SEARCH_DEBOUNCE_MS);
        }
    }

    clearSearch() {
        this.state.searchQuery = "";
        this.state.showSearchOverlay = false;
        const el = document.getElementById("dk-search-input");
        if (el) el.value = "";
    }

    async _globalSearch(query) {
        this.state.showSearchOverlay = true;
        this.state.searchLoading = true;
        this.state.globalSearchResults = [];
        try {
            const results = await this.orm.call(
                "dojo.kiosk.config", "kiosk_search_members", [query]
            );
            // kiosk_search_members returns a plain array
            this.state.globalSearchResults = Array.isArray(results) ? results : (results.members || []);
        } catch (e) {
            this.state.globalSearchResults = [];
        } finally {
            this.state.searchLoading = false;
        }
    }

    closeSearchOverlay() {
        this.state.showSearchOverlay = false;
        this.state.globalSearchResults = [];
    }

    openMemberFromSearch(m) {
        this.state.showSearchOverlay = false;
        this.openMember(m, null);
    }

    // ─── Member open (card click) ─────────────────────────────────

    async openMember(m, sessionId) {
        this._resetIdleTimer();

        if (this.state.instructorMode) {
            // Full detail popup
            this.state.popupSessionId = sessionId;
            this.state.showMemberPopup = true;
            this.state.loadingMember = true;
            this.state.memberDetail = null;
            try {
                const detail = await this.orm.call(
                    "dojo.kiosk.config", "kiosk_get_member_detail", [m.id]
                );
                this.state.memberDetail = detail;
            } catch (e) {
                this._showError("Could not load member details.");
                this.state.showMemberPopup = false;
            } finally {
                this.state.loadingMember = false;
            }
        } else {
            // Student mode: confirm check-in popup
            const sess = this.state.sessions.find(s => s.id === sessionId);
            this.state.checkinMember = m;
            this.state.checkinSessionId = sessionId;
            this.state.checkinSessionName = sess ? sess.name : "";
            this.state.showCheckinPopup = true;
        }
    }

    closeMemberPopup() {
        this.state.showMemberPopup = false;
        this.state.memberDetail = null;
        this.state.popupSessionId = null;
    }

    closeCheckinPopup() {
        this.state.showCheckinPopup = false;
        this.state.checkinMember = null;
        this.state.checkinSessionId = null;
        this.state.checkinSessionName = "";
    }

    // ─── Check-in / Checkout ─────────────────────────────────────

    async confirmCheckin(partnerId, sessionId) {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "dojo.kiosk.config", "kiosk_checkin_partner", [partnerId, sessionId]
            );
            this.closeCheckinPopup();
            this._showSuccess(res.message || "Checked in!");
            await this._loadRoster();
        } catch (e) {
            this._showError(e.message || "Check-in failed.");
        } finally {
            this.state.loading = false;
        }
    }

    async doCheckin(partnerId, sessionId) {
        this.state.loadingMember = true;
        try {
            const res = await this.orm.call(
                "dojo.kiosk.config", "kiosk_checkin_partner", [partnerId, sessionId]
            );
            this._showSuccess(res.message || "Checked in!");
            await this._refreshMemberDetail(this.state.memberDetail.id);
            await this._loadRoster();
        } catch (e) {
            this._showError(e.message || "Check-in failed.");
        } finally {
            this.state.loadingMember = false;
        }
    }

    async doCheckout(attendanceId, sessionId) {
        this.state.loadingMember = true;
        try {
            await this.orm.call(
                "dojo.kiosk.config", "kiosk_checkout", [attendanceId]
            );
            this._showSuccess("Checked out.");
            await this._refreshMemberDetail(this.state.memberDetail.id);
            await this._loadRoster();
        } catch (e) {
            this._showError(e.message || "Checkout failed.");
        } finally {
            this.state.loadingMember = false;
        }
    }

    async addToRoster(partnerId, sessionId) {
        this.state.loadingMember = true;
        try {
            await this.orm.call(
                "dojo.kiosk.config", "kiosk_add_to_roster", [partnerId, sessionId]
            );
            this._showSuccess("Added to roster.");
            await this._refreshMemberDetail(partnerId);
            await this._loadRoster();
        } catch (e) {
            this._showError(e.message || "Could not add to roster.");
        } finally {
            this.state.loadingMember = false;
        }
    }

    async removeFromRoster(rosterId, sessionId) {
        this.state.loadingMember = true;
        try {
            await this.orm.call(
                "dojo.kiosk.config", "kiosk_remove_from_roster", [rosterId]
            );
            this._showSuccess("Removed from roster.");
            await this._refreshMemberDetail(this.state.memberDetail.id);
            await this._loadRoster();
        } catch (e) {
            this._showError(e.message || "Could not remove from roster.");
        } finally {
            this.state.loadingMember = false;
        }
    }

    async _refreshMemberDetail(partnerId) {
        try {
            const detail = await this.orm.call(
                "dojo.kiosk.config", "kiosk_get_member_detail", [partnerId]
            );
            this.state.memberDetail = detail;
        } catch (e) { /* ignore */ }
    }

    // ─── Barcode scanner ─────────────────────────────────────────

    _onKeydown(ev) {
        // Ignore if typing in a real input (search / PIN)
        if (ev.target && ["INPUT", "SELECT", "TEXTAREA"].includes(ev.target.tagName)) {
            if (ev.target.id !== "dk-barcode-input") return;
        }
        const ch = ev.key;
        if (ch === "Enter") {
            const code = this._barcodeBuffer.trim();
            this._barcodeBuffer = "";
            clearTimeout(this._barcodeTimer);
            if (code.length >= 4) this._handleBarcode(code);
        } else if (ch.length === 1) {
            this._barcodeBuffer += ch;
            clearTimeout(this._barcodeTimer);
            this._barcodeTimer = setTimeout(() => {
                this._barcodeBuffer = "";
            }, BARCODE_DEBOUNCE_MS * 5);
        }
    }

    onBarcodeInput(ev) {
        // Hidden input as fallback for scanners that focus it
        clearTimeout(this._barcodeTimer);
        this._barcodeTimer = setTimeout(() => {
            const code = ev.target.value.trim();
            ev.target.value = "";
            if (code.length >= 4) this._handleBarcode(code);
        }, BARCODE_DEBOUNCE_MS * 3);
    }

    async _handleBarcode(code) {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "dojo.kiosk.config", "kiosk_checkin_barcode", [code]
            );
            if (res.success) {
                this._showSuccess(res.message || "Checked in!");
                await this._loadRoster();
            } else {
                this._showError(res.error || res.message || "Member not found.");
            }
        } catch (e) {
            this._showError("Barcode scan error.");
        } finally {
            this.state.loading = false;
        }
    }

    // ─── Settings (opens kiosk config form in new tab) ────────────

    openSettings() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dojo.kiosk.config",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
        });
    }

    // ─── Toast helpers ───────────────────────────────────────────

    _showSuccess(msg) {
        this.state.toastMessage = msg;
        this.state.showSuccessToast = true;
        this.state.showErrorToast = false;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            this.state.showSuccessToast = false;
        }, TOAST_DURATION_MS);
    }

    _showError(msg) {
        this.state.toastMessage = msg;
        this.state.showErrorToast = true;
        this.state.showSuccessToast = false;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            this.state.showErrorToast = false;
        }, TOAST_DURATION_MS);
    }
}

registry.category("actions").add("dojo_kiosk.kiosk_action", KioskApp);
