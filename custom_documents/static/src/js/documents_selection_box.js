/** @odoo-module **/

import { useState } from "@odoo/owl";
import { SelectionBox } from "@web/views/view_components/selection_box";

/**
 * "N selected" box of the selection bar, counting selected folders too.
 *
 * Folders are not records of the view, so the standard box would only count
 * files and show "0 selected" when only folders are ticked.  It uses the
 * standard template (web.SelectionBox).
 */
export class DocumentsSelectionBox extends SelectionBox {
    static props = { ...SelectionBox.props };

    setup() {
        super.setup();
        this.folderSelection = useState(
            this.env.documentsFolderSelection || { ids: new Set() }
        );
    }

    get nbFolders() {
        return this.folderSelection.ids.size;
    }

    get nbSelected() {
        return super.nbSelected + this.nbFolders;
    }

    get isPageSelected() {
        // "Select all N records" only makes sense for a selection of files.
        return !this.nbFolders && super.isPageSelected;
    }

    onUnselectAll() {
        super.onUnselectAll();
        this.folderSelection.ids.clear();
    }
}
