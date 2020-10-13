# vim: sw=4:ts=4:et:cc=120
#
# ACE Splunk Hunting System
#

import datetime
import re
import logging
import os, os.path

import saq
from saq.splunk import extract_event_timestamp, SplunkQueryObject
from saq.collectors.query_hunter import QueryHunt
from saq.util import *

class SplunkHunt(QueryHunt):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_index_time = bool()

        # supports hash-style comments
        self.strip_comments = True

        # splunk queries can optionally have <include:> directives
        self._query = None
        self.search_id = None
        self.time_spec = None

        # since we have multiple splunk instances, allow config to point to a different one
        self.splunk_config = self.manager.config.get('splunk_config', 'splunk')
        
        self.tool_instance = saq.CONFIG[self.splunk_config]['uri']
        self.timezone = saq.CONFIG[self.splunk_config]['timezone']

        # splunk app/user context
        self.namespace_user = '-' # defaults to wildcards
        self.namespace_app = '-'

    def extract_event_timestamp(self, event):
        return extract_event_timestamp(self, event)

    def formatted_query(self):
        return self.query.replace('{time_spec}', self.time_spec)

    @property
    def query(self):
        if self._query is None:
            return self._query

        result = self._query

        # run the includes you might have
        while True:
            m = re.search(r'<include:([^>]+)>', result)
            if not m:
                break
            
            include_path = m.group(1)
            if not os.path.exists(include_path):
                logging.error(f"rule {self.name} included file {include_path} does not exist")
                break
            else:
                with open(include_path, 'r') as fp:
                    included_text = re.sub(r'^\s*#.*$', '', fp.read().strip(), count=0, flags=re.MULTILINE)
                    result = result.replace(m.group(0), included_text)

        return result

    @query.setter
    def query(self, value):
        self._query = value
    
    def load_from_ini(self, *args, **kwargs):
        config = super().load_from_ini(*args, **kwargs)

        section_rule = config['rule']
        self.use_index_time = section_rule.getboolean('use_index_time')

        # make sure the time spec formatter is available
        # this should really be done at load time...
        if '{time_spec}' not in self.query:
            logging.error(f"missing {{time_spec}} formatter in rule {self.name}")

        # load the namespace names for app and user if they are defined
        # if they are default then the default wildcard is used in the url for the API
        if 'splunk_app_context' in section_rule:
            self.namespace_app = section_rule['splunk_app_context']
        if 'splunk_user_context' in section_rule:
            self.namespace_user = section_rule['splunk_user_context']

    def execute_query(self, start_time, end_time, unit_test_query_results=None):
        tz = pytz.timezone(self.timezone)

        earliest = start_time.astimezone(tz).strftime('%m/%d/%Y:%H:%M:%S')
        latest = end_time.astimezone(tz).strftime('%m/%d/%Y:%H:%M:%S')

        if self.use_index_time:
            self.time_spec = f'_index_earliest = {earliest} _index_latest = {latest}'
        else:
            self.time_spec = f'earliest = {earliest} latest = {latest}'

        query = self.formatted_query()

        logging.info(f"executing hunt {self.name} with start time {earliest} end time {latest}")

        if unit_test_query_results is not None:
            return unit_test_query_results
        
        searcher = SplunkQueryObject(
            uri=saq.CONFIG[self.splunk_config]['uri'],
            username=saq.CONFIG[self.splunk_config]['username'],
            password=saq.CONFIG[self.splunk_config]['password'],
            max_result_count=self.max_result_count,
            query_timeout=self.query_timeout,
            namespace_user=self.namespace_user,
            namespace_app=self.namespace_app)

        search_result = searcher.query(query)
        self.search_id = searcher.search_id

        if not search_result:
            logging.error(f"search failed for {self}")
            return None

        query_result = searcher.json()
        if query_result is None:
            logging.error(f"search {self} returned no results (usually indicates an issue with the search)")
            return None

        return query_result
