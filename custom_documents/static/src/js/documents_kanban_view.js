/** @odoo-module **/

import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { DocumentsKanbanController } from "./documents_kanban_controller";
import { DocumentsSearchPanel } from "./documents_search_panel";
import { DocumentsKanbanRenderer } from "./documents_kanban_renderer";

export const documentsKanbanView = {
    ...kanbanView,
    Controller: DocumentsKanbanController,
    Renderer: DocumentsKanbanRenderer,
    SearchPanel: DocumentsSearchPanel,
};

registry.category("views").add("documents_kanban", documentsKanbanView);
