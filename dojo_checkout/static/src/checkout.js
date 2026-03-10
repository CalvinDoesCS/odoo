/** @odoo-module **/
/**
 * Dojo Checkout — Progressive-enhancement JS
 *
 * No framework required. Adds:
 *   1. Enrollment-type toggle (adult vs family — show/hide child fields, relabel parent fields)
 *   2. Upsell card toggle (visual selection state)
 *   3. Day-picker card toggle
 */

document.addEventListener("DOMContentLoaded", () => {
    initEnrollmentType();
    initUpsellCards();
    initDayCards();
});

/* ────────────────────────────────────────────────────────────
   ENROLLMENT TYPE — toggle family section, relabel primary fields
──────────────────────────────────────────────────────────── */
function initEnrollmentType() {
    const radios = document.querySelectorAll('input[name="enrollment_type"]');
    if (!radios.length) return;

    const familyFields   = document.getElementById("dojo-family-fields");
    const childNameInput = document.getElementById("child_name");

    const labelMap = {
        member_name:         { adult: "Full Name",          family: "Parent / Guardian Name"  },
        member_email:        { adult: "Email",              family: "Parent / Guardian Email" },
        member_phone:        { adult: "Phone",              family: "Parent / Guardian Phone" },
        label_date_of_birth: { adult: "Date of Birth",      family: "Parent's Date of Birth"  },
    };

    function applyState(type) {
        const isFamily = type === "family";
        if (familyFields) familyFields.style.display = isFamily ? "" : "none";
        if (childNameInput) childNameInput.required = isFamily;

        for (const [id, labels] of Object.entries(labelMap)) {
            const labelEl = document.getElementById(id)
                || document.querySelector(`label[for="${id}"]`);
            if (!labelEl) continue;
            for (const node of labelEl.childNodes) {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    node.textContent = labels[type] + " ";
                    break;
                }
            }
        }

        document.querySelectorAll(".dojo-enroll-option").forEach((card) => {
            const radio = card.querySelector("input[type='radio']");
            const active = radio && radio.checked;
            card.style.borderColor = active ? "#0d6efd" : "";
            card.style.background  = active ? "#f0f6ff" : "";
        });
    }

    radios.forEach((r) => r.addEventListener("change", () => applyState(r.value)));
    const checked = document.querySelector('input[name="enrollment_type"]:checked');
    if (checked) applyState(checked.value);
}

/* ────────────────────────────────────────────────────────────
   UPSELL CARDS — toggle visual selection
──────────────────────────────────────────────────────────── */
function initUpsellCards() {
    const container = document.getElementById("dojo-upsells");
    if (!container) return;

    container.querySelectorAll(".dojo-upsell-card").forEach((card) => {
        const checkbox = card.querySelector(".dojo-upsell-check");
        if (!checkbox) return;

        if (checkbox.checked) card.classList.add("dojo-selected");

        card.addEventListener("click", () => {
            checkbox.checked = !checkbox.checked;
            card.classList.toggle("dojo-selected", checkbox.checked);
        });

        // Prevent double-toggle when clicking directly on checkbox
        checkbox.addEventListener("click", (e) => e.stopPropagation());
    });
}

/* ────────────────────────────────────────────────────────────
   DAY PICKER — toggle visual selection
──────────────────────────────────────────────────────────── */
function initDayCards() {
    document.querySelectorAll(".dojo-day-card").forEach((card) => {
        const checkbox = card.querySelector(".dojo-day-check");
        if (!checkbox) return;

        if (checkbox.checked) card.classList.add("dojo-selected");

        card.addEventListener("click", () => {
            checkbox.checked = !checkbox.checked;
            card.classList.toggle("dojo-selected", checkbox.checked);
        });

        checkbox.addEventListener("click", (e) => e.stopPropagation());
    });
}
