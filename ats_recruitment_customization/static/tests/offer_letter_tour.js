/** @odoo-module **/

import tour from 'web_tour.tour';

tour.register('offer_letter_tour', {
    test: true,
    url: '/web',
}, [

    // ---------------------------------------------------
    // Open Recruitment Module
    // ---------------------------------------------------

    {
        trigger: '.o_app[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
        content: 'Open Recruitment Module',
        run: 'click',
    },

    // ---------------------------------------------------
    // Open Applicants Menu
    // ---------------------------------------------------

    {
        trigger: 'a[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_all_applications"]',
        content: 'Open Applicants',
        run: 'click',
    },

    // ---------------------------------------------------
    // Open First Applicant
    // ---------------------------------------------------

    {
        trigger: '.o_data_row:first',
        content: 'Open Applicant Record',
        run: 'click',
    },

    // ---------------------------------------------------
    // Click Print Button
    // ---------------------------------------------------

    {
        trigger: '.o_cp_action_menus .dropdown-toggle',
        content: 'Open Print Menu',
        run: 'click',
    },

    // ---------------------------------------------------
    // Click Offer Letter Report
    // ---------------------------------------------------

    {
        trigger: 'span:contains("Offer Letter")',
        content: 'Print Offer Letter',
        run: 'click',
    },

]);