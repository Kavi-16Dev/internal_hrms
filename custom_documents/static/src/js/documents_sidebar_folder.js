/** @odoo-module **/

/**
 * Folder currently picked in the left "Workspaces" tree of the search panel
 * (the standard category section on ``folder_id``), or ``false`` when nothing
 * is picked (the "All" root).
 *
 * The main area (folder cards) reads this so it always shows the children of
 * the folder highlighted in the sidebar.
 */
export function getSidebarFolderId(searchModel) {
    if (!searchModel || !searchModel.getSections) {
        return false;
    }
    try {
        const section = searchModel
            .getSections((s) => s.type === "category" && s.fieldName === "folder_id")
            .at(0);
        return (section && section.activeValueId) || false;
    } catch {
        return false;
    }
}
