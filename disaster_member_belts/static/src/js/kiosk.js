/* global KIOSK_SESSION_ID */
'use strict';

// ================================================================
//  Dojo Kiosk – kiosk.js
//  Modes: barcode scan | PIN number pad | name search
// ================================================================

var kiosk = (function () {

    // ---- State --------------------------------------------------
    var sessionId = 0;
    var currentMode = 'barcode';   // 'barcode' | 'pin' | 'name'
    var memberPinVal = '';
    var selectedMember = null;
    var selectedClassSessionId = null;  // chosen in class-select overlay
    var resetTimer = null;
    var barcodeBuffer = '';
    var barcodeTimer = null;

    // Instructor gate PIN state
    var gatePinVal = '';

    // ---- Belt badge colours ------------------------------------
    var BELT_CLASS = {
        'white': 'belt-white',
        'yellow': 'belt-yellow',
        'orange': 'belt-orange',
        'green': 'belt-green',
        'blue': 'belt-blue',
        'purple': 'belt-purple',
        'brown': 'belt-brown',
        'red': 'belt-red',
        'black': 'belt-black',
    };

    // ---- Helpers -----------------------------------------------
    function debounce(fn, ms) {
        var t;
        return function () {
            var args = arguments;
            clearTimeout(t);
            t = setTimeout(function () { fn.apply(null, args); }, ms);
        };
    }

    function el(id) { return document.getElementById(id); }

    function getCsrf() {
        var m = document.querySelector('meta[name=csrf-token]');
        return m ? m.getAttribute('content') : '';
    }

    function postJson(url, data) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: data }),
        }).then(function (r) { return r.json(); })
            .then(function (resp) { return resp.result || resp; });
    }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ---- Clock -------------------------------------------------
    function updateClock() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2, '0');
        var m = String(now.getMinutes()).padStart(2, '0');
        var clockEl = el('kiosk-clock');
        if (clockEl) clockEl.textContent = h + ':' + m;
    }

    // ---- Session selector --------------------------------------
    function selectSession(val) {
        sessionId = parseInt(val, 10) || 0;
    }

    // ---- Mode switching ----------------------------------------
    function setMode(mode) {
        currentMode = mode;

        ['barcode', 'pin', 'name'].forEach(function (m) {
            var tab = el('tab-' + m);
            if (tab) tab.classList.toggle('active', m === mode);
        });

        var areas = {
            barcode: el('kiosk-barcode-area'),
            pin: el('kiosk-pin-area'),
            name: el('kiosk-name-area'),
        };
        Object.keys(areas).forEach(function (k) {
            if (areas[k]) areas[k].style.display = (k === mode) ? '' : 'none';
        });

        if (mode === 'barcode') {
            barcodeBuffer = '';
            var bi = el('kiosk-barcode-input');
            if (bi) bi.focus();
        } else if (mode === 'pin') {
            resetMemberPin();
        } else if (mode === 'name') {
            var ni = el('kiosk-name-input');
            if (ni) { ni.value = ''; ni.focus(); }
            showIdle();
        }
    }

    // ---- Barcode mode ------------------------------------------
    function onDocumentKeydown(e) {
        if (currentMode !== 'barcode') return;
        if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Alt' || e.key === 'Meta') return;

        if (e.key === 'Enter') {
            clearTimeout(barcodeTimer);
            var barcode = barcodeBuffer.trim();
            barcodeBuffer = '';
            if (barcode.length >= 2) {
                lookupAndCheckin('barcode', barcode);
            }
        } else if (e.key.length === 1) {
            barcodeBuffer += e.key;
            clearTimeout(barcodeTimer);
            barcodeTimer = setTimeout(function () { barcodeBuffer = ''; }, 1500);
        }
    }

    // ---- PIN mode ----------------------------------------------
    function memberPinKey(k) {
        clearTimeout(resetTimer);
        if (k === 'back') {
            memberPinVal = memberPinVal.slice(0, -1);
        } else if (memberPinVal.length < 4) {
            memberPinVal += String(k);
        }
        updatePinDots();
        var err = el('member-pin-error');
        if (err) err.style.display = 'none';

        if (memberPinVal.length === 4) {
            resetTimer = setTimeout(function () {
                lookupAndCheckin('pin', memberPinVal);
            }, 400);
        }
    }

    function updatePinDots() {
        for (var i = 0; i < 4; i++) {
            var dot = el('mpd-' + i);
            if (dot) dot.classList.toggle('filled', i < memberPinVal.length);
        }
    }

    function resetMemberPin() {
        memberPinVal = '';
        updatePinDots();
        clearTimeout(resetTimer);
        var err = el('member-pin-error');
        if (err) err.style.display = 'none';
    }

    // ---- Lookup & identify (barcode / PIN) ---------------------
    function lookupAndCheckin(mode, value) {
        postJson('/dojo/kiosk/lookup', { mode: mode, value: value })
            .then(function (data) {
                if (data.error || !data.member) {
                    if (mode === 'pin') {
                        var err = el('member-pin-error');
                        if (err) err.style.display = 'block';
                        resetTimer = setTimeout(resetMemberPin, 2000);
                    } else {
                        var icon = document.querySelector('.kiosk-barcode-icon');
                        if (icon) {
                            icon.classList.add('kiosk-barcode-error-flash');
                            setTimeout(function () {
                                icon.classList.remove('kiosk-barcode-error-flash');
                            }, 600);
                        }
                    }
                    return;
                }
                var m = data.member;
                selectedMember = { id: m.id, name: m.name, belt: m.belt_rank, avatar: m.avatar_url };
                showClassSelect(selectedMember);
            })
            .catch(function () {
                var err = el('member-pin-error');
                if (err) err.style.display = 'block';
            });
    }

    // ---- Name search mode --------------------------------------
    function fetchSearch(query) {
        query = (query || '').trim();
        if (!query) { showIdle(); return; }
        postJson('/dojo/kiosk/search', { query: query, session_id: sessionId })
            .then(function (data) {
                if (data.error) { showNoResults(); return; }
                renderResults(data.members || []);
            })
            .catch(showNoResults);
    }

    var debouncedSearch = debounce(fetchSearch, 300);

    function renderResults(members) {
        var results = el('kiosk-results');
        var idle = el('kiosk-idle');
        if (!results) return;

        if (!members.length) {
            results.innerHTML = '<div class="kiosk-no-results">No members found — ask staff for help.</div>';
            results.style.display = 'block';
            if (idle) idle.style.display = 'none';
            return;
        }

        results.innerHTML = members.map(function (m) {
            var beltCls = BELT_CLASS[m.belt_rank] || 'belt-white';
            var name = escHtml(m.name);
            var belt = escHtml((m.belt_rank || 'white').replace('_', ' '));
            // JSON.stringify inside a double-quoted HTML attribute: encode " as &quot;
            function attrJson(v) { return JSON.stringify(v).replace(/"/g, '&quot;'); }
            return '<div class="kiosk-member-card" ' +
                'onclick="kiosk.onMemberTap(' + m.id + ',' + attrJson(m.name) + ',' +
                attrJson(m.belt_rank || 'white') + ',' + attrJson(m.avatar_url || '') + ')">' +
                '<img class="kiosk-member-avatar" src="' + escHtml(m.avatar_url || '/web/image/res.partner/' + m.id + '/avatar_128') + '" alt="">' +
                '<div class="kiosk-member-name">' + name + '</div>' +
                '<div class="kiosk-member-belt ' + beltCls + '">' + belt + '</div>' +
                '</div>';
        }).join('');

        results.style.display = 'grid';
        if (idle) idle.style.display = 'none';
    }

    function showIdle() {
        var results = el('kiosk-results');
        var idle = el('kiosk-idle');
        if (results) { results.style.display = 'none'; results.innerHTML = ''; }
        if (idle) idle.style.display = 'flex';
    }

    function showNoResults() {
        var results = el('kiosk-results');
        if (results) {
            results.innerHTML = '<div class="kiosk-no-results">No members found — ask staff for help.</div>';
            results.style.display = 'block';
        }
    }

    function onMemberTap(id, name, belt, avatar) {
        selectedMember = { id: id, name: name, belt: belt, avatar: avatar };
        showClassSelect(selectedMember);
    }

    // ---- Check-in POST -----------------------------------------
    function doCheckin() {
        if (!selectedMember) return;
        var targetSession = selectedClassSessionId || sessionId;
        postJson('/dojo/kiosk/checkin', {
            partner_id: selectedMember.id,
            session_id: targetSession,
        }).then(function (data) {
            hideClassSelect();
            showConfirm(data);
        }).catch(function () {
            hideClassSelect();
            showConfirm({
                status: 'error', name: selectedMember.name,
                belt_rank: selectedMember.belt, avatar_url: selectedMember.avatar,
            });
        });
    }

    // ---- Class-select overlay ----------------------------------
    function showClassSelect(member) {
        selectedClassSessionId = null;

        var overlay = el('kiosk-class-select');
        if (!overlay) {
            // No overlay in DOM — fall back to direct check-in
            doCheckin();
            return;
        }

        // Populate member identity section
        var avatarEl = el('kiosk-cs-avatar');
        var nameEl = el('kiosk-cs-name');
        var beltEl = el('kiosk-cs-belt');
        if (avatarEl) avatarEl.src = member.avatar || '/web/image/res.partner/' + member.id + '/avatar_128';
        if (nameEl) nameEl.textContent = member.name;
        if (beltEl) {
            var beltText = (member.belt || 'white').replace('_', ' ');
            beltEl.textContent = beltText;
            beltEl.className = 'kiosk-cs-belt ' + (BELT_CLASS[member.belt] || 'belt-white');
        }

        // Disable check-in button until session chosen
        var btn = el('kiosk-cs-checkin-btn');
        if (btn) btn.disabled = true;

        // Show overlay immediately (with spinner state)
        var sessionsEl = el('kiosk-cs-sessions');
        var noSessEl = el('kiosk-cs-no-session');
        var histEl = el('kiosk-cs-history');
        if (sessionsEl) sessionsEl.innerHTML = '<div class="kiosk-cs-loading">Loading…</div>';
        if (histEl) histEl.innerHTML = '';
        overlay.style.display = 'flex';

        // Fetch member info (sessions + history)
        postJson('/dojo/kiosk/member_info', { partner_id: member.id })
            .then(function (data) {
                var sessions = data.sessions || [];
                var history = data.history || [];

                // Render session cards
                if (!sessions.length) {
                    if (sessionsEl) sessionsEl.innerHTML = '';
                    if (noSessEl) noSessEl.style.display = 'block';
                } else {
                    if (noSessEl) noSessEl.style.display = 'none';
                    if (sessionsEl) {
                        sessionsEl.innerHTML = sessions.map(function (s) {
                            var spotsLeft = Math.max(0, s.capacity - s.count);
                            var isFull = spotsLeft === 0;
                            var isRestricted = s.eligible === false;
                            var isDisabled = isFull || isRestricted;
                            var spotLabel = isFull
                                ? '<span class="kiosk-cs-full">Full</span>'
                                : isRestricted
                                    ? '<span class="kiosk-cs-restricted">🔒 ' + escHtml(s.reason || 'Restricted') + '</span>'
                                    : '<span class="kiosk-cs-spots">' + spotsLeft + ' spots left</span>';
                            var cardClass = 'kiosk-cs-session-card' +
                                (isFull ? ' kiosk-cs-card-full' : '') +
                                (isRestricted ? ' kiosk-cs-card-restricted' : '');
                            return '<div class="' + cardClass + '"' +
                                (isDisabled ? '' : ' onclick="kioskSelectClass(' + s.id + ', \'' + escHtml(s.name) + '\')"') +
                                '>' +
                                '<div class="kiosk-cs-card-top">' +
                                '  <div class="kiosk-cs-card-name">' + escHtml(s.name) + '</div>' +
                                '  <div class="kiosk-cs-card-time">' + escHtml(s.time) + '</div>' +
                                '</div>' +
                                '<div class="kiosk-cs-card-bottom">' +
                                '  <span class="kiosk-cs-card-type">' + escHtml(s.type || '') + '</span>' +
                                (s.instructor ? '<span class="kiosk-cs-card-instructor">' + escHtml(s.instructor) + '</span>' : '') +
                                spotLabel +
                                '</div>' +
                                '</div>';
                        }).join('');
                    }
                }

                // Render history
                if (histEl) {
                    if (!history.length) {
                        histEl.innerHTML = '<div class="kiosk-cs-no-history">No recent classes</div>';
                    } else {
                        histEl.innerHTML = history.map(function (h) {
                            return '<div class="kiosk-cs-hist-row">' +
                                '<span class="kiosk-cs-hist-date">' + escHtml(h.date) + '</span>' +
                                '<span class="kiosk-cs-hist-class">' + escHtml(h.class) + '</span>' +
                                '</div>';
                        }).join('');
                    }
                }

                // If only one session and not full, auto-select it
                if (sessions.length === 1 && sessions[0].count < sessions[0].capacity) {
                    selectClass(sessions[0].id, sessions[0].name);
                }
            })
            .catch(function () {
                if (sessionsEl) sessionsEl.innerHTML = '<div class="kiosk-cs-loading">Could not load classes</div>';
            });

        // Auto-dismiss after 60 seconds of inactivity
        clearTimeout(resetTimer);
        resetTimer = setTimeout(hideClassSelectAndReset, 60000);
    }

    function hideClassSelect() {
        var overlay = el('kiosk-class-select');
        if (overlay) overlay.style.display = 'none';
        selectedClassSessionId = null;
    }

    function hideClassSelectAndReset() {
        hideClassSelect();
        resetToSearch();
    }

    function selectClass(sessId, sessName) {
        selectedClassSessionId = sessId;
        // Highlight the selected card
        document.querySelectorAll('.kiosk-cs-session-card').forEach(function (c) {
            c.classList.remove('kiosk-cs-card-selected');
        });
        var all = document.querySelectorAll('.kiosk-cs-session-card');
        all.forEach(function (c) {
            // Re-render via onclick attribute contains the id
            if (c.getAttribute('onclick') && c.getAttribute('onclick').indexOf('' + sessId) !== -1) {
                c.classList.add('kiosk-cs-card-selected');
            }
        });

        var btn = el('kiosk-cs-checkin-btn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Check In to ' + sessName + ' →';
        }

        clearTimeout(resetTimer);
        resetTimer = setTimeout(hideClassSelectAndReset, 60000);
    }

    function classCheckin() {
        if (!selectedClassSessionId) return;
        clearTimeout(resetTimer);
        doCheckin();
    }

    function notMe() {
        clearTimeout(resetTimer);
        hideClassSelect();
        selectedMember = null;
        resetToSearch();
    }

    // ---- Instructor gate PIN -----------------------------------
    function openInstructor(evt) {
        if (evt) evt.preventDefault();
        gatePinVal = '';
        _renderGateDots();
        var gateErr = el('kiosk-gate-error');
        if (gateErr) gateErr.style.display = 'none';
        var gate = el('kiosk-instructor-gate');
        if (gate) gate.style.display = 'flex';
    }

    function gatePinKey(k) {
        if (k === 'back') {
            gatePinVal = gatePinVal.slice(0, -1);
        } else if (gatePinVal.length < 4) {
            gatePinVal += String(k);
        }
        _renderGateDots();
        var gateErr = el('kiosk-gate-error');
        if (gateErr) gateErr.style.display = 'none';

        if (gatePinVal.length === 4) {
            postJson('/dojo/kiosk/instructor/auth', { pin: gatePinVal })
                .then(function (data) {
                    if (data.ok) {
                        window.location.href = '/dojo/kiosk/instructor';
                    } else {
                        if (gateErr) gateErr.style.display = 'block';
                        setTimeout(function () {
                            gatePinVal = '';
                            _renderGateDots();
                            if (gateErr) gateErr.style.display = 'none';
                        }, 1800);
                    }
                });
        }
    }

    function _renderGateDots() {
        for (var i = 0; i < 4; i++) {
            var d = el('gdot-' + i);
            if (d) d.classList.toggle('filled', i < gatePinVal.length);
        }
    }

    function closeGate() {
        gatePinVal = '';
        _renderGateDots();
        var gate = el('kiosk-instructor-gate');
        if (gate) gate.style.display = 'none';
    }

    // ---- Confirm overlay ---------------------------------------
    function showConfirm(data) {
        var overlay = el('kiosk-confirm');
        if (!overlay) return;

        var beltCls = BELT_CLASS[data.belt_rank] || 'belt-white';
        var name = data.name || (selectedMember && selectedMember.name) || '';
        var belt = (data.belt_rank || 'white').replace('_', ' ');
        var avatar = data.avatar_url || (selectedMember ? selectedMember.avatar : '') || '';

        var msgEl = el('kiosk-confirm-msg');
        if (data.status === 'ok') {
            msgEl.textContent = '✅ Checked In!';
            msgEl.className = 'kiosk-confirm-msg';
        } else if (data.status === 'already_in') {
            msgEl.textContent = '👋 Already Checked In';
            msgEl.className = 'kiosk-confirm-msg already-in';
        } else if (data.status === 'no_session') {
            msgEl.textContent = '⚠️ No active session selected';
            msgEl.className = 'kiosk-confirm-msg already-in';
        } else if (data.error === 'belt_rank_too_low') {
            var reqBelt = (data.required_belt || '').replace('_', ' ');
            msgEl.textContent = '🥋 Belt Rank Too Low — Requires ' + (reqBelt || 'higher') + ' belt';
            msgEl.className = 'kiosk-confirm-msg already-in';
        } else if (data.error === 'not_enrolled') {
            msgEl.textContent = '📋 Not Enrolled — See front desk to register';
            msgEl.className = 'kiosk-confirm-msg already-in';
        } else {
            msgEl.textContent = '⚠️ Something went wrong';
            msgEl.className = 'kiosk-confirm-msg already-in';
        }

        el('kiosk-confirm-name').textContent = name;

        var beltEl = el('kiosk-confirm-belt');
        beltEl.textContent = belt;
        beltEl.className = 'kiosk-confirm-belt ' + beltCls;

        // Show which class they checked into
        var classEl = el('kiosk-confirm-class');
        if (classEl) {
            var classSelect = el('kiosk-cs-checkin-btn');
            // Extract class name from the button text
            var btnText = classSelect ? classSelect.textContent : '';
            var classMatch = btnText.replace('Check In to ', '').replace(' →', '');
            classEl.textContent = classMatch && classMatch !== 'Check In →' ? classMatch : '';
        }

        el('kiosk-confirm-avatar').src = avatar ||
            '/web/image/res.partner/' + (selectedMember ? selectedMember.id : 0) + '/avatar_128';

        var bar = el('kiosk-timer-bar');
        if (bar) {
            bar.style.animation = 'none';
            void bar.offsetWidth;
            bar.style.animation = '';
        }

        overlay.style.display = 'flex';
        clearTimeout(resetTimer);
        resetTimer = setTimeout(resetToSearch, 5000);
    }

    function resetToSearch() {
        var overlay = el('kiosk-confirm');
        if (overlay) overlay.style.display = 'none';

        selectedMember = null;
        selectedClassSessionId = null;

        if (currentMode === 'barcode') {
            barcodeBuffer = '';
            var bi = el('kiosk-barcode-input');
            if (bi) bi.focus();
        } else if (currentMode === 'pin') {
            resetMemberPin();
        } else {
            var ni = el('kiosk-name-input');
            if (ni) { ni.value = ''; ni.focus(); }
            var clr = el('kiosk-clear');
            if (clr) clr.style.display = 'none';
            showIdle();
        }
    }

    function clearInput() {
        var input = el('kiosk-name-input');
        if (input) { input.value = ''; input.focus(); }
        var btn = el('kiosk-clear');
        if (btn) btn.style.display = 'none';
        showIdle();
    }

    // ---- Init --------------------------------------------------
    function init() {
        sessionId = (typeof KIOSK_SESSION_ID !== 'undefined') ? (KIOSK_SESSION_ID || 0) : 0;

        updateClock();
        setInterval(updateClock, 10000);

        // Start in barcode mode
        setMode('barcode');

        // Global keydown captures barcode scanner input
        document.addEventListener('keydown', onDocumentKeydown);

        // Click barcode area → re-focus hidden input
        var barcodeArea = el('kiosk-barcode-area');
        if (barcodeArea) {
            barcodeArea.addEventListener('click', function () {
                var bi = el('kiosk-barcode-input');
                if (bi) bi.focus();
            });
        }

        // Name search input
        var nameInput = el('kiosk-name-input');
        if (nameInput) {
            nameInput.addEventListener('input', function () {
                var val = this.value;
                var clr = el('kiosk-clear');
                if (clr) clr.style.display = val ? 'block' : 'none';
                debouncedSearch(val);
            });
        }

        // Tap outside confirm card to dismiss
        var overlay = el('kiosk-confirm');
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    clearTimeout(resetTimer);
                    resetToSearch();
                }
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        onMemberTap: onMemberTap,
        clearInput: clearInput,
        selectSession: selectSession,
        setMode: setMode,
        memberPinKey: memberPinKey,
        // class select
        selectClass: selectClass,
        classCheckin: classCheckin,
        notMe: notMe,
        // instructor gate
        openInstructor: openInstructor,
        gatePinKey: gatePinKey,
        closeGate: closeGate,
    };

})();

function kioskSelectSession(val) { kiosk.selectSession(val); }
function kioskClear() { kiosk.clearInput(); }
function kioskSetMode(m) { kiosk.setMode(m); }
function kioskMemberPinKey(k) { kiosk.memberPinKey(k); }
function kioskSelectClass(id, n) { kiosk.selectClass(id, n); }
function kioskClassCheckin() { kiosk.classCheckin(); }
function kioskNotMe() { kiosk.notMe(); }
function kioskOpenInstructor(ev) { kiosk.openInstructor(ev); return false; }
function kioskGatePinKey(k) { kiosk.gatePinKey(k); }
function kioskCloseGate() { kiosk.closeGate(); }
