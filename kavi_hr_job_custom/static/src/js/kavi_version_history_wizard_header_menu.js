/** @odoo-module **/

/**
 * The "Salary" (hr.applicant) / "Menu" (hr.job) dropdown in the
 * "Version History" popup must sit in the dialog's own header row,
 * immediately to the right of the "Version History" title text
 * (NOT next to the close (X) button on the far right).
 *
 * It is written in the view's XML as a normal <div class="o_kavi_vh_header_menu">
 * inside the wizard's form body. That div cannot be positioned into the
 * header with pure CSS because its DOM parent, `.modal-body`, has
 * `overflow-y: auto`, which clips anything that visually escapes it -
 * regardless of what it is CSS-positioned relative to.
 *
 * So instead we physically move the DOM node into `.modal-header`, right
 * after the `.modal-title` element, as soon as it appears, using a
 * MutationObserver. Wrapped in try/catch throughout so that, even in an
 * unexpected DOM shape, this file can never throw and break the rest of
 * the JS asset bundle.
 */

(function () {
    "use strict";

    var MENU_SELECTOR = ".o_kavi_vh_header_menu";
    var MOVED_CLASS = "o_kavi_vh_header_menu_mounted";
    var TITLE_SELECTOR = ".modal-header .modal-title";

    function relocate(menuEl) {
        try {
            if (!menuEl || menuEl.classList.contains(MOVED_CLASS)) {
                return;
            }
            var modalContent = menuEl.closest(".modal-content");
            if (!modalContent) {
                return;
            }
            var header = modalContent.querySelector(".modal-header");
            if (!header) {
                return;
            }
            var title = header.querySelector(TITLE_SELECTOR);
            if (title) {
                // Place it right after the title text, e.g.
                // "Version History  [Salary v]      ...      X"
                if (title.nextSibling) {
                    header.insertBefore(menuEl, title.nextSibling);
                } else {
                    header.appendChild(menuEl);
                }
            } else {
                // Fallback: no recognizable title node, just prepend.
                header.insertBefore(menuEl, header.firstChild);
            }
            menuEl.classList.add(MOVED_CLASS);
            // Visible in the browser console (F12) so it's easy to confirm
            // this script actually ran after an upgrade + hard refresh.
            /* eslint-disable-next-line no-console */
            console.info("kavi_hr_job_custom: header menu moved next to title", menuEl);
        } catch (err) {
            // Never let a DOM-shape surprise break the wider JS bundle.
            /* eslint-disable-next-line no-console */
            console.warn("kavi_hr_job_custom: header menu relocation skipped", err);
        }
    }

    function scan(root) {
        try {
            if (!root || typeof root.querySelectorAll !== "function") {
                return;
            }
            if (root.matches && root.matches(MENU_SELECTOR)) {
                relocate(root);
            }
            var found = root.querySelectorAll(MENU_SELECTOR);
            for (var i = 0; i < found.length; i++) {
                relocate(found[i]);
            }
        } catch (err) {
            /* eslint-disable-next-line no-console */
            console.warn("kavi_hr_job_custom: header menu scan skipped", err);
        }
    }

    try {
        var observer = new MutationObserver(function (mutations) {
            for (var m = 0; m < mutations.length; m++) {
                var added = mutations[m].addedNodes;
                for (var n = 0; n < added.length; n++) {
                    var node = added[n];
                    if (node.nodeType === 1) {
                        scan(node);
                    }
                }
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });

        // Catch any instance already in the DOM when this script runs.
        scan(document.body);

        // Extra safety net: for the first few seconds after any dialog
        // opens, also re-scan on a short interval. This covers the rare
        // case where the menu div and the title land in the DOM in two
        // separate mutation batches (menu div present, title not yet),
        // which would otherwise fall through to the "no title" fallback.
        var pollCount = 0;
        var pollId = setInterval(function () {
            pollCount += 1;
            scan(document.body);
            if (pollCount >= 20) { // ~5s at 250ms
                clearInterval(pollId);
            }
        }, 250);
    } catch (err) {
        /* eslint-disable-next-line no-console */
        console.warn("kavi_hr_job_custom: header menu observer failed to start", err);
    }
})();
