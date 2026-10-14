/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { DocumentsListController } from "./documents_list_controller";
import { DocumentsSearchPanel } from "./documents_search_panel";
import { DocumentsListRenderer } from "./documents_list_renderer";

export const documentsListView = {
    ...listView,
    Controller: DocumentsListController,
    Renderer: DocumentsListRenderer,
    SearchPanel: DocumentsSearchPanel,
};

registry.category("views").add("documents_list", documentsListView);
