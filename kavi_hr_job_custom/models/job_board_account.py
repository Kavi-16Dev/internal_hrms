# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:  # pragma: no cover - requests ships with Odoo itself
    requests = None


class HrJobBoardAccount(models.Model):
    """Credential store for external Job Board integrations.

    Each record is one connection to one external job board/aggregator
    (Adzuna, Careerjet, WhatJobs, Talent.com, LinkedIn Basic, Google).
    `name` (Account Name) is a free-text field, e.g. "Adzuna - India";
    the provider it refers to is auto-detected from that text into the
    stored `provider` field (see `_detect_provider`/PROVIDER_KEYWORDS
    below). Only the credential fields relevant to the detected
    `provider` are shown on the form (controlled via `invisible` on the
    view), and `action_test_connection` dispatches on `provider` too.

    NOTE ON "TEST CONNECTION": every integration below exposes a
    different real-world API contract, and the exact endpoint/parameters
    your account uses can vary by plan and region. `action_test_connection`
    performs a best-effort reachability/credential check against each
    provider's publicly documented endpoint. Treat it as a starting point
    and adjust `_test_<name>()` below once you have live credentials
    from that job board, rather than as a guaranteed-correct final
    integration.
    """
    _name = 'hr.job.board.account'
    _description = 'Job Board Account / Integration'
    _order = 'sequence, name'

 
    PROVIDER_SELECTION = [
        ('adzuna', 'Adzuna'),
        ('careerjet', 'Careerjet'),
        ('whatjobs', 'WhatJobs'),
        ('talent', 'Talent.com'),
        ('linkedin_basic', 'LinkedIn Basic'),
        ('google', 'Google (Google for Jobs)'),
    ]

   
    PROVIDER_KEYWORDS = [
        ('adzuna', ['adzuna']),
        ('careerjet', ['careerjet']),
        ('whatjobs', ['whatjobs', 'what jobs']),
        ('talent', ['talent.com', 'talent']),
        ('linkedin_basic', ['linkedin']),
        ('google', ['google']),
    ]

    name = fields.Char(
        string='Account Name', required=True,
        help='Free-text name for this account, e.g. "Adzuna - India" or '
             '"LinkedIn Basic - US". Must contain the provider name '
             '(Adzuna, Careerjet, WhatJobs, Talent.com, LinkedIn Basic or '
             'Google) so Odoo can recognize which credential fields to '
             'show and which Test Connection check to run.')
    provider = fields.Selection(
        PROVIDER_SELECTION, string='Provider', compute='_compute_provider',
        store=True, readonly=True,
        help='Automatically detected from the Account Name above. '
             'Determines which credential fields are shown below and '
             'which "Test Connection" check runs. Not directly editable - '
             'change the Account Name text to change this.')
    job_board_id = fields.Many2one(
        'hr.job.board', string='Job Board', ondelete='cascade',
        help='The Job Board (e.g. LinkedIn, Naukri, Indeed) this '
             'integration account connects to.')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)

    # --- Connection status -------------------------------------------------
    state = fields.Selection([
        ('not_connected', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], string='Status', default='not_connected', readonly=True, copy=False)
    last_connection_date = fields.Datetime(
        string='Last Tested On', readonly=True, copy=False)
    last_connection_message = fields.Char(
        string='Last Test Result', readonly=True, copy=False)

   
    app_id = fields.Char(
        string='App ID',
        help='Adzuna: the App ID issued when you register at '
             'https://developer.adzuna.com/')
    api_key = fields.Char(
        string='API Key',
        help='Adzuna App Key / WhatJobs API Key / Talent.com API Key / '
             'Google API Key, depending on the Job Board selected above.')
    affiliate_id = fields.Char(
        string='Affiliate ID',
        help='Careerjet: the affiliate ID (affid) issued by Careerjet.')
    publisher_id = fields.Char(
        string='Publisher ID',
        help='WhatJobs: the Publisher ID for your WhatJobs feed account.')
    partner_id = fields.Char(
        string='Partner ID',
        help='Talent.com: the Partner ID for your Talent.com feed account.')
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    access_token = fields.Char(
        string='Access Token',
        help='LinkedIn Basic / Google: OAuth access token, if the '
             'integration uses token-based auth rather than a feed URL.')
    refresh_token = fields.Char(string='Refresh Token')
    client_id = fields.Char(
        string='Client ID', help='Google: OAuth 2.0 Client ID.')
    client_secret = fields.Char(
        string='Client Secret', help='Google: OAuth 2.0 Client Secret.')
    service_account_json = fields.Text(
        string='Service Account JSON',
        help='Google: paste the Service Account key JSON here if using '
             'Google Cloud Talent Solution instead of OAuth.')
    feed_url = fields.Char(
        string='Job Feed URL',
        help='LinkedIn Basic / Google for Jobs: the public XML/JSON job '
             'feed URL that the job board is configured to crawl.')
    company_page_url = fields.Char(
        string='Company Page URL',
        help='LinkedIn Basic: URL of your LinkedIn Company Page, used to '
             'match the feed to your organization.')
    locale = fields.Char(
        string='Locale / Country Code', default='en_GB',
        help='Careerjet / Adzuna: locale or two-letter country code the '
             'account posts jobs into, e.g. "en_GB", "in", "us".')

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'An Account with this Account Name already exists for this company.'),
    ]

    @api.depends('name')
    def _compute_provider(self):
        for record in self:
            record.provider = record._detect_provider(record.name)

    @api.model
    def _detect_provider(self, account_name):
        """Return the provider key (e.g. 'adzuna') recognized inside the
        given Account Name text, or False if none of the known providers
        are mentioned. See PROVIDER_KEYWORDS above for the matching
        rules."""
        text = (account_name or '').lower()
        for provider_key, keywords in self.PROVIDER_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return provider_key
        return False

    @api.onchange('name')
    def _onchange_name_reset_state(self):
        for record in self:
            record.state = 'not_connected'
            record.last_connection_message = False

    # --- Test Connection ---------------------------------------------------
    def action_test_connection(self):
        self.ensure_one()
        if not self.provider:
            raise UserError(_(
                'Odoo could not recognize a known provider in the Account '
                'Name "%s". Make sure it contains one of: Adzuna, '
                'Careerjet, WhatJobs, Talent.com, LinkedIn Basic or '
                'Google.') % (self.name or ''))
        method_name = '_test_%s' % self.provider
        test_method = getattr(self, method_name, None)
        if not test_method:
            raise UserError(_('No connection test is defined for this Job Board yet.'))

        vals = {'last_connection_date': fields.Datetime.now()}
        try:
            message = test_method()
            vals.update(state='connected', last_connection_message=message or _('Connected successfully.'))
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface any provider/network error to the user
            _logger.warning('Job Board connection test failed for %s: %s', self.name, exc)
            vals.update(state='error', last_connection_message=str(exc)[:250])
        self.write(vals)
        return True

    def _require(self, *field_names):
        missing = [self._fields[f].string for f in field_names if not self[f]]
        if missing:
            raise UserError(_('Please fill in: %s') % ', '.join(missing))

    def _get_requests(self):
        if requests is None:
            raise UserError(_('The "requests" Python library is not available on this server.'))
        return requests

    def _test_adzuna(self):
        """Adzuna Search API - see https://developer.adzuna.com/"""
        self._require('app_id', 'api_key')
        req = self._get_requests()
        country = (self.locale or 'gb').lower()
        url = 'https://api.adzuna.com/v1/api/jobs/%s/search/1' % country
        resp = req.get(url, params={
            'app_id': self.app_id,
            'app_key': self.api_key,
            'results_per_page': 1,
        }, timeout=10)
        if resp.status_code != 200:
            raise UserError(_('Adzuna returned HTTP %s. Check the App ID / App Key.') % resp.status_code)
        return _('Adzuna credentials accepted (HTTP 200).')

    def _test_careerjet(self):
        """Careerjet public search API - requires only an affiliate ID."""
        self._require('affiliate_id')
        req = self._get_requests()
        resp = req.get('http://public.api.careerjet.net/search', params={
            'affid': self.affiliate_id,
            'keywords': 'test',
            'pagesize': 1,
            'locale_code': self.locale or 'en_GB',
        }, timeout=10)
        if resp.status_code != 200:
            raise UserError(_('Careerjet returned HTTP %s. Check the Affiliate ID.') % resp.status_code)
        return _('Careerjet affiliate ID accepted (HTTP 200).')

    def _test_whatjobs(self):
        """WhatJobs feed API - adjust endpoint/params per your account's docs."""
        self._require('publisher_id', 'api_key')
        req = self._get_requests()
        resp = req.get('https://api.whatjobs.com/api/v1/jobs.json', params={
            'publisher': self.publisher_id,
            'apikey': self.api_key,
            'limit': 1,
        }, timeout=10)
        if resp.status_code != 200:
            raise UserError(_('WhatJobs returned HTTP %s. Check the Publisher ID / API Key.') % resp.status_code)
        return _('WhatJobs credentials accepted (HTTP 200).')

    def _test_talent(self):
        """Talent.com feed API - adjust endpoint/params per your account's docs."""
        self._require('partner_id', 'api_key')
        req = self._get_requests()
        resp = req.get('https://api.talent.com/v1/jobs', params={
            'partner_id': self.partner_id,
            'api_key': self.api_key,
            'limit': 1,
        }, timeout=10)
        if resp.status_code != 200:
            raise UserError(_('Talent.com returned HTTP %s. Check the Partner ID / API Key.') % resp.status_code)
        return _('Talent.com credentials accepted (HTTP 200).')

    def _test_linkedin_basic(self):
        """LinkedIn Basic ("Limited Listings") does not use API auth - it
        crawls a public job feed you host. This checks the feed URL is
        publicly reachable, which is the only thing LinkedIn itself needs."""
        self._require('feed_url')
        req = self._get_requests()
        resp = req.get(self.feed_url, timeout=10)
        if resp.status_code != 200:
            raise UserError(_('The Job Feed URL returned HTTP %s. LinkedIn Basic needs it to be publicly reachable.') % resp.status_code)
        return _('Job Feed URL is reachable (HTTP 200). Submit it in LinkedIn Recruiter/Campaign Manager.')

    def _test_google(self):
        """Google for Jobs (structured-data feed) or Cloud Talent Solution
        (OAuth/service account), depending on what's filled in."""
        if self.feed_url:
            req = self._get_requests()
            resp = req.get(self.feed_url, timeout=10)
            if resp.status_code != 200:
                raise UserError(_('The Job Feed URL returned HTTP %s.') % resp.status_code)
            return _('Job Feed URL is reachable (HTTP 200).')
        self._require('client_id', 'client_secret')
        return _('Google OAuth credentials are filled in. Run the OAuth '
                  'consent flow separately to obtain an Access Token before '
                  'calling the Cloud Talent Solution API.')
