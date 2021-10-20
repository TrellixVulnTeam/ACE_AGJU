# vim: sw=4:ts=4:et

import os
import os.path
import logging
import re
import sys
import json

import saq
from saq.error import report_exception
from saq.analysis import Analysis, Observable
from saq.modules import AnalysisModule
from saq.email import is_local_email_domain
from saq.constants import *
import saq.ldap
import saq.util

class UserTagAnalysis(Analysis):
    def initialize_details(self):
        self.details = None

    @property
    def jinja_should_render(self):
        return False

class UserTaggingAnalyzer(AnalysisModule):
    @property
    def generated_analysis_type(self):
        return UserTagAnalysis

    @property
    def valid_observable_types(self):
        return F_USER

    @property
    def json_path(self):
        return os.path.join(saq.SAQ_HOME, self.config['json_path'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mapping = None # dict of key = username (lowercase), value = [ tags ]
        self.watch_file(self.json_path, self.load_tags)

    def load_tags(self):
        # if we haven't loaded it or if it has changed since the last time we loaded it
        logging.debug("loading {}".format(self.json_path))
        with open(self.json_path, 'r') as fp:
            self.mapping = json.load(fp)

    def execute_analysis(self, user):

        analysis = self.create_analysis(user)

        # does this user ID exist in our list of userIDs to tag?
        if user.value.lower().strip() in self.mapping:
            for tag in self.mapping[user.value.lower().strip()]:
                user.add_tag(tag)

        return True

class EmailAddressAnalysis(Analysis):
    """Who is the user associated to this email address?"""

    def initialize_details(self):
        self.details = []

    def generate_summary(self):
        if self.details is not None and len(self.details) > 0:
            users = []
            for entry in self.details:
                if 'attributes' in entry and 'displayName' in entry['attributes'] and 'cn' in entry['attributes']:
                    users.append(f"{entry['attributes']['displayName']} ({entry['attributes']['cn']})") 
            desc = ", ".join(users)
            return f"Email Analysis - {desc}"
        return None

class EmailAddressAnalyzer(AnalysisModule):
    @property
    def generated_analysis_type(self):
        return EmailAddressAnalysis

    @property
    def valid_observable_types(self):
        return F_EMAIL_ADDRESS

    def execute_analysis(self, email_address):
        analysis = self.create_analysis(email_address)
        analysis.details = saq.ldap.lookup_email_address(email_address.value)
        if len(analysis.details) == 0:
            return False
        for entry in analysis.details:
            if 'attributes' not in entry or 'cn' not in entry['attributes']:
                continue
            analysis.add_observable(F_USER, entry['attributes']['cn'])
        return True

class UserAnalysis(Analysis):
    """What is the contact information for this user?  What is their position?  Who do they work for?"""

    def initialize_details(self):
        return None # free form from ldap query

    @property
    def jinja_template_path(self):
        return "analysis/user.html"

    def generate_summary(self):
        if not self.details:
            return None

        if not self.details['ldap']:
            return None

        return "User Analysis - {} - {} - {} - {} - {}".format(
            self.details['ldap']['displayName'] if 'displayName' in self.details['ldap'] else '',
            self.details['ldap']['company'] if 'company' in self.details['ldap'] else '',
            self.details['ldap']['l'] if 'l' in self.details['ldap'] else '',
            self.details['ldap']['division'] if 'division' in self.details['ldap'] else '',
            self.details['ldap']['title'] if 'title' in self.details['ldap'] else '')

class UserAnalyzer(AnalysisModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag_mappings = {}
        if 'ldap_group_tags' in saq.CONFIG:
            for tag in saq.CONFIG['ldap_group_tags']:
                self.tag_mappings[tag] = saq.CONFIG['ldap_group_tags'][tag].split(',')

    @property
    def generated_analysis_type(self):
        return UserAnalysis

    @property
    def valid_observable_types(self):
        return F_USER

    def execute_analysis(self, user):
        analysis = self.create_analysis(user)
        analysis.details = {}
        analysis.details['ldap'] = saq.ldap.lookup_user(user.value)
        if analysis.details['ldap'] is None:
            logging.error(f"Failed to fetch ldap info for {user.value}")
            return False

        # get manager info and determine if user is executive
        top_user = saq.CONFIG['ldap']['top_user']
        if 'manager_cn' in analysis.details['ldap'] and analysis.details['ldap']['manager_cn'] is not None:
            analysis.details['manager_ldap'] = saq.ldap.lookup_user(analysis.details['ldap']['manager_cn'])
            if analysis.details['manager_ldap'] is None:
                logging.error(f"Failed to fetch manger ldap info for {user.value}")
            elif 'manager_cn' in analysis.details['manager_ldap'] and analysis.details['manager_ldap']['manager_cn'] is not None:
                if top_user in [user.value.lower(), analysis.details['ldap']['manager_cn'].lower(), analysis.details['manager_ldap']['manager_cn'].lower()]:
                    user.add_tag("executive")

        # check for privileged access
        analysis.details['ldap']['entitlements'] = []
        if 'memberOf' in analysis.details['ldap'] and analysis.details['ldap']['memberOf'] is not None:
            for group in analysis.details['ldap']['memberOf']:
                privileged = False # now used for any highlighting
                for tag, patterns in self.tag_mappings.items():
                    for pattern in patterns:
                        if pattern in group:
                            user.add_tag(tag)
                            privileged = True
                            break
                analysis.details['ldap']['entitlements'].append({'group':group, 'privileged':privileged})

        # did we get an email address?
        if 'mail' in analysis.details['ldap'] and analysis.details['ldap']['mail'] is not None:
            analysis.add_observable(F_EMAIL_ADDRESS, analysis.details['ldap']['mail'])

        return True
