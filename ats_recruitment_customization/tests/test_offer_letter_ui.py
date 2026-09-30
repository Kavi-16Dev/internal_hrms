from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestOfferLetterUI(HttpCase):

    def test_offer_letter_ui(self):
        """Test Offer Letter UI Tour"""
        pass
        # self.start_tour(
        #     "/web",
        #     'offer_letter_tour',
        #     login='admin'
        # )