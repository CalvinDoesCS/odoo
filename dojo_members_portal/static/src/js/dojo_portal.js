(function () {
    "use strict";

    /* ── Constants ──────────────────────────────────────────────────────── */
    var LEVEL = {
        beginner:     { label: "Beginner",     cls: "bg-success" },
        intermediate: { label: "Intermediate", cls: "bg-warning text-dark" },
        advanced:     { label: "Advanced",     cls: "bg-danger" },
        all:          { label: "All Levels",   cls: "bg-secondary" },
    };
    var STATUS = {
        registered: { label: "Registered", cls: "bg-success" },
        waitlist:   { label: "Waitlist",    cls: "bg-warning text-dark" },
        cancelled:  { label: "Cancelled",   cls: "bg-secondary" },
    };
    var ATT_STATE = {
        pending: { label: "Pending", cls: "bg-secondary" },
        present: { label: "Present", cls: "bg-success" },
        absent:  { label: "Absent",  cls: "bg-danger" },
        excused: { label: "Excused", cls: "bg-warning text-dark" },
    };
    var LOG_STATUS = {
        present: { label: "Present", cls: "bg-success" },
        late:    { label: "Late",    cls: "bg-warning text-dark" },
        absent:  { label: "Absent",  cls: "bg-danger" },
        excused: { label: "Excused", cls: "bg-secondary" },
    };
    var LEVEL_CLR  = { beginner:"#198754", intermediate:"#ffc107", advanced:"#dc3545", all:"#6c757d" };
    var STATUS_CLR = { registered:"#198754", waitlist:"#ffc107", cancelled:"#6c757d" };
    var LOG_CLR    = { present:"#198754", late:"#ffc107", absent:"#dc3545", excused:"#6c757d" };

    var TAB_TITLES = { schedule:"Class Schedule", enrollments:"My Enrollments", attendance:"Attendance History", household:"My Household", billing:"Billing" };

    function b(map, key)  { return map[key] || { label: key || "\u2014", cls: "bg-secondary" }; }
    function esc(s)       { return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
    function fmtDt(iso) {
        if (!iso) return "\u2014";
        var d = new Date(iso.indexOf("T") !== -1 ? iso + "Z" : iso);
        if (isNaN(d)) return iso;
        return d.toLocaleString("en-US", { weekday:"short", month:"short", day:"numeric", year:"numeric", hour:"numeric", minute:"2-digit" });
    }
    function fmtDate(iso) {
        if (!iso) return "\u2014";
        var d = new Date(iso.indexOf("T") !== -1 ? iso : iso + "T00:00:00");
        if (isNaN(d)) return iso;
        return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
    }
    function fmtMoney(amount, currency) {
        if (amount == null) return "\u2014";
        try { return new Intl.NumberFormat("en-US", { style: "currency", currency: currency || "USD" }).format(amount); }
        catch(e) { return (currency || "") + " " + Number(amount).toFixed(2); }
    }
    function fetchJson(url) {
        return fetch(url, { credentials: "same-origin" })
            .then(function(r){ return r.ok ? r.json() : {}; })
            .catch(function()  { return {}; });
    }

    /* ── Card builders ──────────────────────────────────────────────────── */
    function sessionCard(s) {
        var lvl = b(LEVEL, s.level);
        var clr = LEVEL_CLR[s.level] || "#6c757d";
        var pct = s.capacity ? Math.round(s.seats_taken / s.capacity * 100) : 0;
        return '<div class="col">' +
          '<div class="card dojo-activity-card h-100" data-type="session" data-id="' + s.id + '">' +
            '<div class="dojo-card-accent" style="background:' + esc(clr) + '"></div>' +
            '<div class="card-body d-flex flex-column p-3">' +
              '<div class="d-flex justify-content-between align-items-center mb-2">' +
                '<span class="badge ' + esc(lvl.cls) + '">' + esc(lvl.label) + '</span>' +
                (s.duration_minutes ? '<small class="text-muted fw-semibold">' + esc(s.duration_minutes) + '&nbsp;min</small>' : '') +
              '</div>' +
              '<h6 class="card-title fw-bold mb-2 lh-sm">' + esc(s.name) + '</h6>' +
              '<div class="vstack gap-1 text-muted small mb-3">' +
                '<div><i class="fa fa-calendar-o me-1"></i>' + esc(fmtDt(s.start_datetime)) + '</div>' +
                (s.instructor ? '<div><i class="fa fa-user me-1"></i>' + esc(s.instructor) + '</div>' : '') +
              '</div>' +
              '<div class="mt-auto">' +
                '<div class="d-flex justify-content-between mb-1">' +
                  '<small class="text-muted">Seats</small>' +
                  '<small class="text-muted fw-semibold">' + esc(s.seats_taken) + '/' + esc(s.capacity) + '</small>' +
                '</div>' +
                '<div class="progress" style="height:5px;"><div class="progress-bar bg-primary" role="progressbar" style="width:' + pct + '%"></div></div>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>';
    }

    function enrollmentCard(e) {
        var st  = b(STATUS, e.status);
        var at  = b(ATT_STATE, e.attendance_state);
        var clr = STATUS_CLR[e.status] || "#6c757d";
        return '<div class="col">' +
          '<div class="card dojo-activity-card h-100" data-type="enrollment" data-id="' + e.id + '">' +
            '<div class="dojo-card-accent" style="background:' + esc(clr) + '"></div>' +
            '<div class="card-body p-3">' +
              '<div class="d-flex justify-content-between align-items-start mb-2">' +
                '<span class="badge ' + esc(st.cls) + '">' + esc(st.label) + '</span>' +
                '<span class="badge ' + esc(at.cls) + '">' + esc(at.label) + '</span>' +
              '</div>' +
              '<h6 class="card-title fw-bold mb-2 lh-sm">' + esc(e.session_name) + '</h6>' +
              '<div class="vstack gap-1 text-muted small">' +
                '<div><i class="fa fa-calendar-o me-1"></i>' + esc(fmtDt(e.start_datetime)) + '</div>' +
                (e.instructor  ? '<div><i class="fa fa-user me-1"></i>'           + esc(e.instructor)  + '</div>' : '') +
                (e.member_name ? '<div><i class="fa fa-graduation-cap me-1"></i>' + esc(e.member_name) + '</div>' : '') +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>';
    }

    function attendanceCard(log) {
        var ls  = b(LOG_STATUS, log.status);
        var clr = LOG_CLR[log.status] || "#6c757d";
        return '<div class="col">' +
          '<div class="card dojo-activity-card h-100" data-type="attendance" data-id="' + log.id + '">' +
            '<div class="dojo-card-accent" style="background:' + esc(clr) + '"></div>' +
            '<div class="card-body p-3">' +
              '<div class="mb-2"><span class="badge ' + esc(ls.cls) + '">' + esc(ls.label) + '</span></div>' +
              '<h6 class="card-title fw-bold mb-2 lh-sm">' + esc(log.session_name || "Session") + '</h6>' +
              '<div class="vstack gap-1 text-muted small">' +
                '<div><i class="fa fa-clock-o me-1"></i>' + esc(fmtDt(log.checkin_datetime)) + '</div>' +
                (log.member_name ? '<div><i class="fa fa-graduation-cap me-1"></i>' + esc(log.member_name) + '</div>' : '') +
                (log.note        ? '<div class="fst-italic"><i class="fa fa-comment-o me-1"></i>' + esc(log.note) + '</div>' : '') +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>';
    }

    /* ── Household tab ───────────────────────────────────────────────────── */
    function householdTabHtml(data, isParent) {
        if (!data || data.error || !data.members) {
            return '<div class="alert alert-info">Household information unavailable.</div>';
        }
        var html = '<div class="d-flex justify-content-between align-items-center mb-3">';
        if (data.household_name) {
            html += '<h6 class="fw-semibold mb-0"><i class="fa fa-home me-2"></i>' + esc(data.household_name) + '</h6>';
        } else {
            html += '<h6 class="fw-semibold mb-0 text-muted">Household</h6>';
        }
        if (isParent) {
            html += '<button class="btn btn-outline-secondary btn-sm" id="dojoEditHouseholdBtn"><i class="fa fa-pencil me-1"></i>Edit</button>';
        }
        html += '</div>';
        if (!data.members.length) {
            return html + '<div class="alert alert-info">No members found.</div>';
        }
        html += '<div class="row row-cols-1 row-cols-md-2 g-3">';
        data.members.forEach(function(m) {
            html += '<div class="col"><div class="card h-100">';
            html += '<div class="card-header d-flex justify-content-between align-items-center">';
            html += '<strong>' + esc(m.name) + '</strong>';
            html += '<span class="badge bg-secondary small text-capitalize">' + esc(m.role || '') + '</span>';
            html += '</div><div class="card-body p-3">';
            // ── Subscription plan ──────────────────────────────────────────────
            var plan = m.plan;
            html += '<p class="text-muted small fw-semibold mb-1">Membership Plan</p>';
            if (plan) {
                var PLAN_STATE = { active:'bg-success', paused:'bg-warning text-dark', cancelled:'bg-secondary', draft:'bg-info text-dark', expired:'bg-danger' };
                html += '<div class="d-flex align-items-center gap-2 mb-3">';
                html += '<span class="fw-semibold small">' + esc(plan.name) + '</span>';
                html += '<span class="badge ' + esc(PLAN_STATE[plan.state] || 'bg-secondary') + ' small">' + esc((plan.state || '').replace(/_/g,' ')) + '</span>';
                if (plan.billing_period) {
                    html += '<span class="text-muted small">' + esc(fmtMoney(plan.price, plan.currency)) + ' / ' + esc(plan.billing_period) + '</span>';
                }
                html += '</div>';
            } else {
                html += '<p class="text-muted small fst-italic mb-3">No active plan.</p>';
            }
            // ── Sessions-per-week counter ──────────────────────────────────
            var used    = m.sessions_used_this_week    || 0;
            var allowed = m.sessions_allowed_per_week  || 0;
            html += '<p class="text-muted small fw-semibold mb-1">Sessions This Week</p>';
            if (allowed === 0) {
                html += '<span class="badge bg-success mb-3">Unlimited</span>';
            } else {
                var pct  = Math.min(100, Math.round(used / allowed * 100));
                var clr  = pct >= 100 ? 'bg-danger' : pct >= 75 ? 'bg-warning text-dark' : 'bg-success';
                html += '<div class="d-flex align-items-center gap-2 mb-1">';
                html += '<span class="badge ' + clr + '">' + used + ' / ' + allowed + '</span>';
                html += '<div class="progress flex-grow-1" style="height:6px"><div class="progress-bar ' + clr + '" role="progressbar" style="width:' + pct + '%"></div></div>';
                html += '</div>';
                if (pct >= 100) {
                    html += '<small class="text-danger d-block mb-2"><i class="fa fa-exclamation-triangle me-1"></i>Weekly limit reached</small>';
                }
            }

            // ── Enrolled courses ──────────────────────────────────────────
            if (m.courses && m.courses.length) {
                html += '<p class="text-muted small fw-semibold mb-1 mt-2">Enrolled Courses</p>';
                html += '<div class="d-flex flex-wrap gap-1 mb-3">';
                m.courses.forEach(function(c) {
                    var lvl = b(LEVEL, c.level);
                    html += '<span class="badge ' + esc(lvl.cls) + '" title="' + esc(lvl.label) + '">' + esc(c.name) + '</span>';
                });
                html += '</div>';
            } else {
                html += '<p class="text-muted small fst-italic mb-2">Not enrolled in any courses yet.</p>';
            }

            // ── Emergency contacts ────────────────────────────────────────
            if (m.emergency_contacts && m.emergency_contacts.length) {
                html += '<p class="text-muted small fw-semibold mb-2">Emergency Contacts</p>';
                m.emergency_contacts.forEach(function(ec) {
                    html += '<div class="mb-2">';
                    html += '<div class="fw-semibold small">' + esc(ec.name);
                    if (ec.is_primary) html += ' <span class="badge bg-success" style="font-size:0.6rem">Primary</span>';
                    html += '</div>';
                    html += '<div class="text-muted small">' + esc(ec.relationship || '') + (ec.relationship && ec.phone ? ' &bull; ' : '') + esc(ec.phone || '') + '</div>';
                    if (ec.email) html += '<div class="text-muted small">' + esc(ec.email) + '</div>';
                    html += '</div>';
                });
            } else {
                html += '<p class="text-muted small mb-0">No emergency contacts on file.</p>';
            }
            html += '</div></div></div>';
        });
        html += '</div>';
        return html;
    }

    /* ── Household edit overlay ──────────────────────────────────────────── */
    function openHouseholdEditOverlay(data, members, onSave) {
        var memberOpts = (data.members || []).map(function(m) {
            return '<option value="' + m.id + '">' + esc(m.name) + '</option>';
        }).join('');

        var html = '<h4 class="fw-bold mb-3">Edit Household</h4>';
        html += '<div class="mb-3"><label class="form-label fw-semibold">Household Name</label>';
        html += '<input type="text" class="form-control" id="dojoHHName" value="' + esc(data.household_name || '') + '"/></div>';
        html += '<hr class="my-3"/>';
        html += '<h6 class="fw-semibold mb-2">Add Emergency Contact</h6>';
        if (members.length > 1) {
            html += '<div class="mb-2"><label class="form-label small">For Member</label>';
            html += '<select class="form-select form-select-sm" id="dojoHHMemberSel">' + memberOpts + '</select></div>';
        }
        html += '<div class="row g-2 mb-3">';
        html += '<div class="col-6"><label class="form-label small">Name *</label><input type="text" class="form-control form-control-sm" id="dojoHHCName" placeholder="Full name"/></div>';
        html += '<div class="col-6"><label class="form-label small">Relationship</label><input type="text" class="form-control form-control-sm" id="dojoHHCRel" placeholder="e.g. Mother"/></div>';
        html += '<div class="col-6"><label class="form-label small">Phone *</label><input type="tel" class="form-control form-control-sm" id="dojoHHCPhone" placeholder="+1 555 000 0000"/></div>';
        html += '<div class="col-6"><label class="form-label small">Email</label><input type="email" class="form-control form-control-sm" id="dojoHHCEmail" placeholder="optional"/></div>';
        html += '</div>';
        html += '<div id="dojoHHMsg" class="mb-2 small"></div>';
        html += '<div class="d-flex gap-2"><button class="btn btn-primary btn-sm" id="dojoHHSaveBtn">Save Changes</button><button class="btn btn-secondary btn-sm" id="dojoHHCancelBtn">Cancel</button></div>';

        var el = document.createElement("div");
        el.id = "dojoOverlay"; el.className = "dojo-overlay-backdrop";
        el.innerHTML = '<div class="dojo-overlay-panel" role="dialog" aria-modal="true">' +
            '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" id="dojoOverlayClose" aria-label="Close"></button>' +
            html + '</div>';
        document.body.appendChild(el);
        document.body.classList.add("dojo-overlay-open");
        el.addEventListener("click", function(ev){ if (ev.target === el) closeOverlay(); });
        document.getElementById("dojoOverlayClose").addEventListener("click", closeOverlay);
        document.getElementById("dojoHHCancelBtn").addEventListener("click", closeOverlay);
        document.getElementById("dojoHHSaveBtn").addEventListener("click", function() {
            var saveBtn = document.getElementById("dojoHHSaveBtn");
            var hhName = (document.getElementById("dojoHHName") || {}).value || '';
            var cName  = (document.getElementById("dojoHHCName") || {}).value || '';
            var cRel   = (document.getElementById("dojoHHCRel") || {}).value || '';
            var cPhone = (document.getElementById("dojoHHCPhone") || {}).value || '';
            var cEmail = (document.getElementById("dojoHHCEmail") || {}).value || '';
            var mSel   = document.getElementById("dojoHHMemberSel");
            var mId    = mSel ? parseInt(mSel.value, 10) : (members.length ? members[0].id : null);
            var payload = { household_name: hhName };
            if (cName && cPhone) { payload.new_contact = { member_id: mId, name: cName, relationship: cRel, phone: cPhone, email: cEmail }; }
            saveBtn.disabled = true; saveBtn.textContent = "Saving\u2026";
            fetch('/my/dojo/household/save', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            }).then(function(r){ return r.json(); }).then(function(res){
                var msg = document.getElementById("dojoHHMsg");
                if (res.ok) {
                    if (msg) msg.innerHTML = '<span class="text-success"><i class="fa fa-check me-1"></i>Saved!</span>';
                    setTimeout(function(){ closeOverlay(); if (onSave) onSave(); }, 700);
                } else {
                    if (msg) msg.innerHTML = '<span class="text-danger">' + esc(res.error || 'Could not save.') + '</span>';
                    saveBtn.disabled = false; saveBtn.textContent = "Save Changes";
                }
            });
        });
    }

    /* ── Billing tab ─────────────────────────────────────────────────────── */
    function billingTabHtml(data, isParent) {
        // ── Family Plan placeholder ───────────────────────────────────────
        var html = '<div class="card mb-4" style="max-width:480px">';
        html += '<div class="card-body p-4 text-center">';
        html += '<i class="fa fa-credit-card fa-3x text-muted mb-3"></i>';
        html += '<h5 class="fw-bold mb-1">Family Plan</h5>';
        html += '<p class="text-muted mb-0">Family billing and plan management are coming soon.</p>';
        html += '<span class="badge bg-secondary mt-2">Future Implementation</span>';
        html += '</div></div>';

        if (!data || data.error) return html;

        // ── Payment method card ───────────────────────────────────────────
        var pm = data.payment_method || {};
        html += '<h6 class="fw-semibold mb-3">Payment Method</h6>';
        if (pm.has_card) {
            var brand = pm.brand || 'Card';
            var last4 = pm.last4 || '0000';
            html += '<div class="card mb-4" style="max-width:340px;background:linear-gradient(135deg,#243742 0%,#3a5c6e 100%);color:#fff;border:none">';
            html += '<div class="card-body p-4">';
            html += '<div class="d-flex justify-content-between align-items-start mb-4">';
            html += '<span class="fw-bold fs-6">' + esc(brand) + '</span>';
            html += '<i class="fa fa-credit-card fa-lg opacity-75"></i>';
            html += '</div>';
            html += '<div class="mb-3" style="letter-spacing:0.18em;font-size:1.05rem;font-family:monospace">';
            html += '\u2022\u2022\u2022\u2022 \u2022\u2022\u2022\u2022 \u2022\u2022\u2022\u2022 ' + esc(last4);
            html += '</div>';
            html += '<div class="d-flex justify-content-between">';
            html += '<small class="opacity-75">Expires ' + esc(pm.expiry || '\u2014') + '</small>';
            if (isParent) html += '<small class="opacity-75">Contact dojo to update</small>';
            html += '</div>';
            html += '</div></div>';
            if (isParent) {
                html += '<button class="btn btn-dark btn-sm mb-4" id="dojoAddToWallet" style="background:#000;border-radius:4px;padding:8px 16px">';
                html += '<img src="https://pay.google.com/about/static/images/social/gp_logo.svg" height="18" style="vertical-align:middle;margin-right:6px" alt="">';
                html += 'Add to Google Wallet</button>';
            }
        } else {
            html += '<div class="alert alert-warning d-flex align-items-center gap-2 mb-4" style="max-width:340px">';
            html += '<i class="fa fa-exclamation-triangle"></i>';
            html += '<span>No payment method on file. Contact the dojo to set up billing.</span>';
            html += '</div>';
        }

        // ── Invoice history ───────────────────────────────────────────────
        var invoices = data.invoices || [];
        html += '<h6 class="fw-semibold mb-3 mt-2">Invoice History</h6>';
        if (!invoices.length) {
            html += '<div class="alert alert-info py-2">No invoices yet.</div>';
        } else {
            html += '<div class="table-responsive"><table class="table table-sm table-hover">';
            html += '<thead class="table-light"><tr><th>Invoice #</th><th>Date</th><th>Amount</th><th>Status</th><th></th></tr></thead><tbody>';
            invoices.forEach(function(inv) {
                var bcls = inv.state === 'posted' ? 'bg-success' : inv.state === 'cancel' ? 'bg-danger' : 'bg-secondary';
                var blbl = inv.state === 'posted' ? 'Paid' : inv.state === 'cancel' ? 'Cancelled' : 'Draft';
                html += '<tr>';
                html += '<td class="small">' + esc(inv.name || '\u2014') + '</td>';
                html += '<td class="small">' + esc(fmtDate(inv.date)) + '</td>';
                html += '<td class="small fw-semibold">' + esc(fmtMoney(inv.amount, inv.currency)) + '</td>';
                html += '<td><span class="badge ' + esc(bcls) + '">' + esc(blbl) + '</span></td>';
                html += '<td><a href="/my/dojo/invoices/' + inv.id + '/pdf" class="btn btn-sm btn-outline-secondary py-0 px-2"><i class="fa fa-download"></i></a></td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        }
        return html;
    }

    function openBillingPlanOverlay(plans, currentPlanId, onSave) {
        var plansHtml = (plans || []).map(function(p) {
            var active = p.id === currentPlanId;
            return '<label class="d-flex align-items-start gap-2 p-3 mb-2 rounded border ' +
                (active ? 'border-primary bg-primary bg-opacity-10' : 'border-secondary-subtle') + '">' +
                '<input type="radio" name="dojoBillingPlan" value="' + p.id + '"' + (active ? ' checked' : '') + ' class="form-check-input mt-1"/>' +
                '<span><span class="fw-semibold d-block">' + esc(p.name) + '</span>' +
                '<span class="text-muted small">' + esc(fmtMoney(p.price, p.currency)) + ' / ' + esc(p.period) + '</span>' +
                (p.description ? '<span class="text-muted small d-block fst-italic">' + esc(p.description) + '</span>' : '') +
                '</span></label>';
        }).join('');
        var html = '<h4 class="fw-bold mb-1">Change Plan</h4>';
        html += '<p class="text-muted small mb-3">Select a new plan. Billing updates on the next invoice date.</p>';
        html += '<div class="mb-3">' + (plansHtml || '<p class="text-muted">No plans available.</p>') + '</div>';
        html += '<div id="dojoPlanMsg" class="mb-2 small"></div>';
        html += '<div class="d-flex gap-2"><button class="btn btn-primary btn-sm" id="dojoPlanSaveBtn">Update Plan</button>';
        html += '<button class="btn btn-secondary btn-sm" id="dojoPlanCancelBtn">Cancel</button></div>';
        var el = document.createElement("div");
        el.id = "dojoOverlay"; el.className = "dojo-overlay-backdrop";
        el.innerHTML = '<div class="dojo-overlay-panel" role="dialog" aria-modal="true">' +
            '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" id="dojoOverlayClose" aria-label="Close"></button>' +
            html + '</div>';
        document.body.appendChild(el);
        document.body.classList.add("dojo-overlay-open");
        el.addEventListener("click", function(ev){ if (ev.target === el) closeOverlay(); });
        document.getElementById("dojoOverlayClose").addEventListener("click", closeOverlay);
        document.getElementById("dojoPlanCancelBtn").addEventListener("click", closeOverlay);
        document.getElementById("dojoPlanSaveBtn").addEventListener("click", function() {
            var checked = el.querySelector('input[name="dojoBillingPlan"]:checked');
            if (!checked) return;
            var saveBtn = document.getElementById("dojoPlanSaveBtn");
            saveBtn.disabled = true; saveBtn.textContent = "Updating\u2026";
            var form = new FormData();
            form.set("plan_id", checked.value);
            fetch("/my/dojo/billing/change-plan", { method: "POST", credentials: "same-origin", body: form })
                .then(function(r){ return r.json(); })
                .then(function(res){
                    var msg = document.getElementById("dojoPlanMsg");
                    if (res.ok) {
                        if (msg) msg.innerHTML = '<span class="text-success"><i class="fa fa-check me-1"></i>Plan updated!</span>';
                        setTimeout(function(){ closeOverlay(); if (onSave) onSave(); }, 700);
                    } else {
                        if (msg) msg.innerHTML = '<span class="text-danger">' + esc(res.error || 'Could not update.') + '</span>';
                        saveBtn.disabled = false; saveBtn.textContent = "Update Plan";
                    }
                });
        });
    }

    function openBillingConfirmOverlay(title, message, btnText, btnCls, onConfirm) {
        var html = '<h4 class="fw-bold mb-3">' + esc(title) + '</h4>';
        html += '<p class="text-muted mb-4">' + esc(message) + '</p>';
        html += '<div id="dojoConfirmMsg" class="mb-3 small"></div>';
        html += '<div class="d-flex gap-2"><button class="btn btn-sm ' + esc(btnCls) + '" id="dojoConfirmOkBtn">' + esc(btnText) + '</button>';
        html += '<button class="btn btn-secondary btn-sm" id="dojoConfirmCancelBtn">Go Back</button></div>';
        var el = document.createElement("div");
        el.id = "dojoOverlay"; el.className = "dojo-overlay-backdrop";
        el.innerHTML = '<div class="dojo-overlay-panel" role="dialog" aria-modal="true">' +
            '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" id="dojoOverlayClose" aria-label="Close"></button>' +
            html + '</div>';
        document.body.appendChild(el);
        document.body.classList.add("dojo-overlay-open");
        el.addEventListener("click", function(ev){ if (ev.target === el) closeOverlay(); });
        document.getElementById("dojoOverlayClose").addEventListener("click", closeOverlay);
        document.getElementById("dojoConfirmCancelBtn").addEventListener("click", closeOverlay);
        document.getElementById("dojoConfirmOkBtn").addEventListener("click", function() {
            var okBtn = document.getElementById("dojoConfirmOkBtn");
            okBtn.disabled = true; okBtn.textContent = "Please wait\u2026";
            function onErr(errMsg) {
                var msgEl = document.getElementById("dojoConfirmMsg");
                if (msgEl) msgEl.innerHTML = '<span class="text-danger">' + esc(errMsg) + '</span>';
                okBtn.disabled = false; okBtn.textContent = btnText;
            }
            onConfirm(onErr);
        });
    }


    /* ── Enrollment section (inside session overlay) ─────────────────────── */
    function enrollSection(session, isParent, members) {
        // Filter to household students who are in this session's course roster
        var eligibleIds = session.eligible_member_ids || [];
        var enrollable = members.filter(function(m) {
            var isStudent = m.role === 'student' || m.role === 'both';
            if (!isStudent) return false;
            // If the server provided an eligible list, enforce it
            if (eligibleIds.length > 0) {
                return eligibleIds.indexOf(m.id) !== -1;
            }
            return true;
        });
        var full = session.capacity > 0 && session.seats_taken >= session.capacity;
        var html = '<div class="border-top pt-3 mt-3" id="dojoEnrollSection">';
        html += '<h6 class="fw-semibold mb-2">Enroll</h6>';
        if (full) {
            html += '<span class="text-muted small">Session is full.</span>';
        } else if (!enrollable.length) {
            var hasStudents = members.some(function(m){ return m.role === 'student' || m.role === 'both'; });
            if (hasStudents) {
                html += '<span class="text-muted small">No household students are enrolled in this course. Ask an instructor to add them to the course roster.</span>';
            } else {
                html += '<span class="text-muted small">No students in your household to enroll.</span>';
            }
        } else if (enrollable.length > 1) {
            var opts = enrollable.map(function(m){ return '<option value="' + m.id + '">' + esc(m.name) + '</option>'; }).join('');
            html += '<div class="d-flex gap-2 align-items-center flex-wrap">';
            html += '<select id="dojoEnrollMemberSel" class="form-select form-select-sm" style="max-width:200px">' + opts + '</select>';
            html += '<button class="btn btn-primary btn-sm" id="dojoEnrollBtn" data-session-id="' + session.id + '">Enroll</button>';
            html += '</div>';
        } else {
            var mid = enrollable[0].id;
            html += '<button class="btn btn-primary btn-sm" id="dojoEnrollBtn" data-session-id="' + session.id + '" data-member-id="' + mid + '">Enroll ' + esc(enrollable[0].name) + '</button>';
        }
        html += '<div id="dojoEnrollMsg" class="mt-2 small"></div></div>';
        return html;
    }

    /* ── Overlay ─────────────────────────────────────────────────────────── */
    function overlayBody(type, item) {
        if (type === "session") {
            var lvl = b(LEVEL, item.level);
            return '<div class="d-flex align-items-center gap-2 mb-3 mt-1">' +
                '<span class="badge fs-6 ' + esc(lvl.cls) + '">' + esc(lvl.label) + '</span>' +
                (item.duration_minutes ? '<small class="text-muted fw-semibold">' + esc(item.duration_minutes) + '&nbsp;min</small>' : '') +
                '</div>' +
                '<h4 class="fw-bold mb-3">' + esc(item.name) + '</h4>' +
                '<dl class="row g-2 mb-0">' +
                '<dt class="col-sm-5 text-muted small">Date &amp; Time</dt><dd class="col-sm-7 small">' + esc(fmtDt(item.start_datetime)) + '</dd>' +
                '<dt class="col-sm-5 text-muted small">Instructor</dt><dd class="col-sm-7 small">'   + esc(item.instructor || "\u2014")       + '</dd>' +
                '<dt class="col-sm-5 text-muted small">Seats</dt><dd class="col-sm-7 small">'        + esc(item.seats_taken) + '/' + esc(item.capacity) + ' taken</dd>' +
                '</dl>' +
                (item.description ? '<div class="mt-3 text-muted small border-top pt-3">' + esc(item.description) + '</div>' : '');
        }
        if (type === "enrollment") {
            var st = b(STATUS, item.status);
            var at = b(ATT_STATE, item.attendance_state);
            return '<div class="d-flex gap-2 mb-3 mt-1"><span class="badge fs-6 ' + esc(st.cls) + '">' + esc(st.label) + '</span><span class="badge fs-6 ' + esc(at.cls) + '">' + esc(at.label) + '</span></div>' +
                '<h4 class="fw-bold mb-3">' + esc(item.session_name) + '</h4>' +
                '<dl class="row g-2 mb-0">' +
                '<dt class="col-sm-5 text-muted small">Member</dt><dd class="col-sm-7 small">'       + esc(item.member_name || "\u2014")          + '</dd>' +
                '<dt class="col-sm-5 text-muted small">Date &amp; Time</dt><dd class="col-sm-7 small">' + esc(fmtDt(item.start_datetime)) + '</dd>' +
                '<dt class="col-sm-5 text-muted small">Instructor</dt><dd class="col-sm-7 small">'   + esc(item.instructor || "\u2014")            + '</dd>' +
                '</dl>';
        }
        var ls = b(LOG_STATUS, item.status);
        return '<div class="mb-3 mt-1"><span class="badge fs-6 ' + esc(ls.cls) + '">' + esc(ls.label) + '</span></div>' +
            '<h4 class="fw-bold mb-3">' + esc(item.session_name || "Session") + '</h4>' +
            '<dl class="row g-2 mb-0">' +
            '<dt class="col-sm-5 text-muted small">Member</dt><dd class="col-sm-7 small">'  + esc(item.member_name || "\u2014")        + '</dd>' +
            '<dt class="col-sm-5 text-muted small">Check-in</dt><dd class="col-sm-7 small">' + esc(fmtDt(item.checkin_datetime)) + '</dd>' +
            (item.note ? '<dt class="col-sm-5 text-muted small">Note</dt><dd class="col-sm-7 small">' + esc(item.note) + '</dd>' : '') +
            '</dl>';
    }

    function openOverlay(type, item, isParent, members, state) {
        var old = document.getElementById("dojoOverlay");
        if (old) old.remove();
        var body = overlayBody(type, item);
        // Enrollment section is only available for parents/guardians
        if (type === "session" && isParent) body += enrollSection(item, isParent, members);
        var el = document.createElement("div");
        el.id = "dojoOverlay"; el.className = "dojo-overlay-backdrop";
        el.innerHTML = '<div class="dojo-overlay-panel" role="dialog" aria-modal="true">' +
            '<button type="button" class="btn-close position-absolute top-0 end-0 m-3" id="dojoOverlayClose" aria-label="Close"></button>' +
            body + '</div>';
        document.body.appendChild(el);
        document.body.classList.add("dojo-overlay-open");
        el.addEventListener("click", function(ev){ if (ev.target === el) closeOverlay(); });
        document.getElementById("dojoOverlayClose").addEventListener("click", closeOverlay);

        var enrollBtn = document.getElementById("dojoEnrollBtn");
        if (enrollBtn) {
            enrollBtn.addEventListener("click", function() {
                var sid = parseInt(enrollBtn.dataset.sessionId, 10);
                var sel = document.getElementById("dojoEnrollMemberSel");
                var mid = sel ? parseInt(sel.value, 10) : parseInt(enrollBtn.dataset.memberId, 10);
                if (!sid || !mid) return;
                enrollBtn.disabled = true; enrollBtn.textContent = "Enrolling\u2026";
                var form = new FormData();
                form.set('session_id', sid); form.set('member_id', mid);
                fetch('/my/dojo/enroll', { method:'POST', credentials:'same-origin', body:form })
                    .then(function(r){ return r.json(); })
                    .then(function(res){
                        var msg = document.getElementById("dojoEnrollMsg");
                        if (res.ok) {
                            if (msg) msg.innerHTML = '<span class="text-success fw-semibold"><i class="fa fa-check me-1"></i>Enrolled successfully!</span>';
                            enrollBtn.classList.replace("btn-primary","btn-success");
                            enrollBtn.textContent = "\u2713 Enrolled";
                            fetchJson("/my/dojo/json/enrollments").then(function(r){ state.enrollments = r.enrollments || []; });
                            fetchJson("/my/dojo/json/schedule").then(function(r){ state.sessions = r.sessions || []; });
                        } else {
                            if (msg) msg.innerHTML = '<span class="text-danger"><i class="fa fa-times me-1"></i>' + esc(res.error || 'Could not enroll.') + '</span>';
                            enrollBtn.disabled = false; enrollBtn.textContent = "Enroll";
                        }
                    }).catch(function(){
                        var msg = document.getElementById("dojoEnrollMsg");
                        if (msg) msg.innerHTML = '<span class="text-danger">An error occurred.</span>';
                        enrollBtn.disabled = false; enrollBtn.textContent = "Enroll";
                    });
            });
        }
    }

    function closeOverlay() {
        var el = document.getElementById("dojoOverlay");
        if (el) el.remove();
        document.body.classList.remove("dojo-overlay-open");
    }

    /* ── Render ──────────────────────────────────────────────────────────── */
    function render(root, state, isParent, members) {
        var TABS = [
            { key:"schedule",    icon:"fa-calendar",    label:"Class Schedule"    },
            { key:"enrollments", icon:"fa-list",         label:"My Enrollments"  },
            { key:"attendance",  icon:"fa-check-circle", label:"Attendance"       },
            { key:"household",   icon:"fa-home",         label:"My Household"    },
        ];
        if (isParent) TABS.push({ key:"billing", icon:"fa-credit-card", label:"Billing" });
        var navHtml = TABS.map(function(t){
            var active = state.activeTab === t.key ? " active" : "";
            var cnt = t.key==="schedule"?state.sessions.length : t.key==="enrollments"?state.enrollments.length : t.key==="attendance"?state.logs.length : t.key==="billing"?(state.billing?(state.billing.invoices||[]).length:0) : 0;
            var badge = cnt ? '<span class="badge bg-secondary ms-1">' + cnt + '</span>' : "";
            return '<li class="nav-item"><button type="button" role="tab" class="nav-link' + active +
                   ' dojo-tab-btn" data-tab="' + t.key + '"><i class="fa ' + t.icon + ' me-1"></i>' + t.label + badge + '</button></li>';
        }).join("");

        var body;
        if (state.loading) {
            body = '<div class="d-flex justify-content-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading\u2026</span></div></div>';
        } else if (state.activeTab === "schedule") {
            if (state.sessions.length) {
                body = '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">' + state.sessions.map(sessionCard).join("") + '</div>';
            } else if (!isParent) {
                body = '<div class="alert alert-info">You haven\'t been assigned to any classes yet. Ask your instructor or parent to enroll you.</div>';
            } else {
                body = '<div class="alert alert-info">No upcoming open sessions right now \u2014 check back soon!</div>';
            }
        } else if (state.activeTab === "enrollments") {
            body = state.enrollments.length
                ? '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">' + state.enrollments.map(enrollmentCard).join("") + '</div>'
                : '<div class="alert alert-info">No enrollments found. Switch to <strong>Class Schedule</strong> to sign up!</div>';
        } else if (state.activeTab === "attendance") {
            body = state.logs.length
                ? '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">' + state.logs.map(attendanceCard).join("") + '</div>'
                : '<div class="alert alert-info">No attendance records yet.</div>';
        } else if (state.activeTab === "billing") {
            body = billingTabHtml(state.billing, isParent);
        } else {
            body = householdTabHtml(state.household, isParent);
        }

        root.innerHTML = '<ul class="nav nav-tabs mb-4" role="tablist">' + navHtml + '</ul>' +
                         '<div id="dojoTabContent">' + body + '</div>';

        root.querySelectorAll(".dojo-tab-btn").forEach(function(btn){
            btn.addEventListener("click", function(){
                state.activeTab = btn.dataset.tab;
                render(root, state, isParent, members);
                var brand = document.querySelector(".o_portal_navbar .navbar-brand");
                if (brand) brand.textContent = TAB_TITLES[btn.dataset.tab] || "Dojo Portal";
            });
        });

        root.querySelectorAll(".dojo-activity-card").forEach(function(card){
            card.addEventListener("click", function(){
                var type = card.dataset.type;
                var id = parseInt(card.dataset.id, 10);
                var item = null;
                if (type === "session")    item = state.sessions.find(function(s){ return s.id === id; });
                if (type === "enrollment") item = state.enrollments.find(function(e){ return e.id === id; });
                if (type === "attendance") item = state.logs.find(function(l){ return l.id === id; });
                if (item) openOverlay(type, item, isParent, members, state);
            });
        });

        var editBtn = document.getElementById("dojoEditHouseholdBtn");
        if (editBtn) {
            editBtn.addEventListener("click", function(){
                openHouseholdEditOverlay(state.household, members, function(){
                    fetchJson("/my/dojo/json/household").then(function(d){
                        state.household = d;
                        render(root, state, isParent, members);
                    });
                });
            });
        }

        // ── Billing action buttons (parents only) ─────────────────────────
        function refreshBilling() {
            fetchJson("/my/dojo/json/billing").then(function(d){
                state.billing = d;
                render(root, state, isParent, members);
            });
        }
        var changePlanBtn = document.getElementById("dojoBillingChangePlan");
        if (changePlanBtn && state.billing && state.billing.plans) {
            changePlanBtn.addEventListener("click", function(){
                openBillingPlanOverlay(
                    state.billing.plans,
                    state.billing.subscription ? state.billing.subscription.plan_id : null,
                    refreshBilling
                );
            });
        }
        var pauseBtn = document.getElementById("dojoBillingPause");
        if (pauseBtn) {
            pauseBtn.addEventListener("click", function(){
                openBillingConfirmOverlay(
                    "Pause Subscription",
                    "Pausing will stop automatic billing. You can resume at any time.",
                    "Pause", "btn-warning",
                    function(onErr){
                        fetch("/my/dojo/billing/pause", { method:"POST", credentials:"same-origin" })
                            .then(function(r){ return r.json(); })
                            .then(function(res){ if (res.ok) { closeOverlay(); refreshBilling(); } else onErr(res.error || "Could not pause."); })
                            .catch(function(){ onErr("An error occurred."); });
                    }
                );
            });
        }
        var resumeBtn = document.getElementById("dojoBillingResume");
        if (resumeBtn) {
            resumeBtn.addEventListener("click", function(){
                fetch("/my/dojo/billing/resume", { method:"POST", credentials:"same-origin" })
                    .then(function(r){ return r.json(); })
                    .then(function(res){ if (res.ok) refreshBilling(); });
            });
        }
        var cancelSubBtn = document.getElementById("dojoBillingCancel");
        if (cancelSubBtn) {
            cancelSubBtn.addEventListener("click", function(){
                openBillingConfirmOverlay(
                    "Cancel Subscription",
                    "This will permanently cancel your membership subscription. This action cannot be undone.",
                    "Yes, Cancel", "btn-danger",
                    function(onErr){
                        fetch("/my/dojo/billing/cancel", { method:"POST", credentials:"same-origin" })
                            .then(function(r){ return r.json(); })
                            .then(function(res){ if (res.ok) { closeOverlay(); refreshBilling(); } else onErr(res.error || "Could not cancel."); })
                            .catch(function(){ onErr("An error occurred."); });
                    }
                );
            });
        }

        // ── Google Wallet push provisioning ──────────────────────────────
        var walletBtn = document.getElementById("dojoAddToWallet");
        if (walletBtn) {
            walletBtn.addEventListener("click", function() {
                walletBtn.disabled = true;
                walletBtn.textContent = "Loading…";
                fetch("/my/dojo/billing/wallet-provision", {credentials: "same-origin"})
                    .then(function(r) { return r.json(); })
                    .then(function(d) {
                        if (d.error) {
                            alert("Error: " + d.error);
                            walletBtn.disabled = false;
                            walletBtn.innerHTML = '<img src="https://pay.google.com/about/static/images/social/gp_logo.svg" height="18" style="vertical-align:middle;margin-right:6px" alt="">Add to Google Wallet';
                            return;
                        }
                        function doProvision() {
                            Stripe(d.publishable_key).pushProvisioning.push({
                                card: d.stripe_card_id,
                                ephemeralKeySecret: d.ephemeral_key_secret,
                            }).then(function(result) {
                                if (result.error) { alert(result.error.message); }
                                walletBtn.disabled = false;
                                walletBtn.innerHTML = '<img src="https://pay.google.com/about/static/images/social/gp_logo.svg" height="18" style="vertical-align:middle;margin-right:6px" alt="">Add to Google Wallet';
                            });
                        }
                        if (!window.Stripe) {
                            var script = document.createElement("script");
                            script.src = "https://js.stripe.com/v3/";
                            script.onload = doProvision;
                            document.head.appendChild(script);
                        } else {
                            doProvision();
                        }
                    })
                    .catch(function() {
                        alert("Network error");
                        walletBtn.disabled = false;
                        walletBtn.innerHTML = '<img src="https://pay.google.com/about/static/images/social/gp_logo.svg" height="18" style="vertical-align:middle;margin-right:6px" alt="">Add to Google Wallet';
                    });
            });
        }
    }

    /* ── Boot ────────────────────────────────────────────────────────────── */
    function boot() {
        var root = document.getElementById("dojo_activities_mount");
        if (!root) return;

        var isParent = root.dataset.isParent === 'true';
        var members  = [];
        try { members = JSON.parse(root.dataset.members || '[]'); } catch(e){}

        var state = {
            activeTab:   root.dataset.tab || "schedule",
            sessions:    [], enrollments: [], logs: [],
            household:   null,
            billing:     null,
            loading:     true,
        };
        render(root, state, isParent, members);

        var brand = document.querySelector(".o_portal_navbar .navbar-brand");
        if (brand) brand.textContent = TAB_TITLES[state.activeTab] || "Dojo Portal";

        var fetches = [
            fetchJson("/my/dojo/json/schedule"),
            fetchJson("/my/dojo/json/enrollments"),
            fetchJson("/my/dojo/json/attendance"),
            fetchJson("/my/dojo/json/household"),
        ];
        if (isParent) fetches.push(fetchJson("/my/dojo/json/billing"));
        Promise.all(fetches).then(function(results){
            state.sessions    = results[0].sessions    || [];
            state.enrollments = results[1].enrollments || [];
            state.logs        = results[2].logs        || [];
            state.household   = results[3];
            state.billing     = isParent ? results[4] : null;
            state.loading     = false;
            render(root, state, isParent, members);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

})();
