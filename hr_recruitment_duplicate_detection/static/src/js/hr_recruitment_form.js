/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { HrRecruitmentForm } from "@website_hr_recruitment/interactions/hr_recruitment_form";

/**
 * Duplicate Email/Phone protection for the public job application form.
 *
 * Rules:
 *   - Existing Email -> submission blocked.
 *   - Existing Phone -> submission blocked.
 *   - Existing Email + Phone -> submission blocked.
 *
 * Candidate Name and LinkedIn are never used for duplicate matching.
 *
 * The browser-side check provides immediate feedback and prevents the form
 * submit before it reaches the server. The Python create()/write() override
 * remains the authoritative server-side protection, so the rule cannot be
 * bypassed by disabling JavaScript or calling the endpoint directly.
 */
patch(HrRecruitmentForm.prototype, {
    setup() {
        super.setup(...arguments);
        this.duplicateContactDetected = false;
    },

    async checkRedundant(targetEl, field, messageContainerEl, keepPreviousWarningMessage = false) {
        // Candidate Name must never trigger duplicate validation.
        if (field === "name") {
            this.hideWarningMessage(targetEl, messageContainerEl);
            return;
        }

        // LinkedIn keeps Odoo's normal validation behavior.
        if (field !== "email" && field !== "phone") {
            return super.checkRedundant(
                targetEl,
                field,
                messageContainerEl,
                keepPreviousWarningMessage,
            );
        }

        const emailInputEl = this.el.querySelector("#recruitment2");
        const phoneInputEl = this.el.querySelector("#recruitment3");
        const email = emailInputEl?.value?.trim() || "";
        const phone = phoneInputEl?.value?.trim() || "";

        if (!email && !phone) {
            this.duplicateContactDetected = false;
            this.hideWarningMessage(targetEl, messageContainerEl);
            return;
        }

        const job_id = document.querySelector("#recruitment7")?.value;
        if (!job_id) {
            this.duplicateContactDetected = false;
            this.hideWarningMessage(targetEl, messageContainerEl);
            return;
        }

        const data = await this.waitFor(rpc(
            "/website_hr_recruitment/check_recent_application",
            {
                field,
                value: targetEl.value,
                job_id,
                email,
                phone,
            },
        ));

        this.duplicateContactDetected = Boolean(data.message);

        if (data.message) {
            this.showWarningMessage(targetEl, messageContainerEl, data.message);
        } else if (!keepPreviousWarningMessage) {
            this.hideWarningMessage(targetEl, messageContainerEl);
        }
    },

    async onApplyButtonClick(ev) {
        /*
         * Stop the native form submission immediately. We must do this
         * BEFORE the async duplicate RPC, otherwise the browser can submit
         * the form while the duplicate check is still running.
         */
        ev.preventDefault();
        ev.stopPropagation();

        const emailInputEl = this.el.querySelector("#recruitment2");
        const phoneInputEl = this.el.querySelector("#recruitment3");
        const email = emailInputEl?.value?.trim() || "";
        const phone = phoneInputEl?.value?.trim() || "";
        const job_id = document.querySelector("#recruitment7")?.value;

        let duplicateMessage = null;

        if (job_id && (email || phone)) {
            const data = await this.waitFor(rpc(
                "/website_hr_recruitment/check_recent_application",
                {
                    field: email ? "email" : "phone",
                    value: email || phone,
                    job_id,
                    email,
                    phone,
                },
            ));
            duplicateMessage = data.message || null;
        }

        if (duplicateMessage) {
            this.duplicateContactDetected = true;

            const warningTarget = emailInputEl || phoneInputEl;
            if (warningTarget && this.warningMessageEl) {
                this.showWarningMessage(
                    warningTarget,
                    this.warningMessageEl,
                    duplicateMessage,
                );
                warningTarget.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                });
            }
            return false;
        }

        this.duplicateContactDetected = false;

        /*
         * No duplicate was found, so hand off entirely to Odoo's normal
         * Apply-button logic. The base implementation does its own field
         * validation AND performs the actual submission itself (an AJAX
         * POST to /website/form/hr.applicant) - it does NOT rely on the
         * click's native default action to submit the form.
         *
         * We must NOT also call form.submit() here. Doing so fires a
         * second, raw native submission straight to the <form> element's
         * static action URL (/website/form/, with no model segment and no
         * CSRF token attached, since that's only ever meant to be posted
         * via the JS/AJAX path). That extra submission is rejected almost
         * instantly with "Bad Request: Session expired (invalid CSRF
         * token)" - visible to the user - even though the legitimate AJAX
         * submission from super() succeeds a moment later in the
         * background. Simply returning the base method's result avoids
         * that duplicate, invalid request entirely.
         */
        return super.onApplyButtonClick(ev);
    },
});
