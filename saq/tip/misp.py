import logging

from pymisp.api import PyMISP, MISPAttribute, MISPEvent, MISPTag
from typing import List, Union

import saq

from saq.constants import *
from saq.indicators import Indicator
from saq.tip.base import TIP


class MISP(TIP):
    def __init__(self):
        super().__init__()

        self.ioc_type_mappings = {
            I_DOMAIN: 'domain',
            I_EMAIL_ATTACHMENT_NAME: 'filename',
            I_EMAIL_CC_ADDRESS: 'email-dst',
            I_EMAIL_FROM_ADDRESS: 'email-src',
            I_EMAIL_FROM_ADDRESS_DOMAIN: 'domain',
            I_EMAIL_MESSAGE_ID: 'email-message-id',
            I_EMAIL_SUBJECT: 'email-subject',
            I_EMAIL_TO_ADDRESS: 'email-dst',
            I_EMAIL_X_AUTH_ID: 'email-src',
            I_EMAIL_X_MAILER: 'email-x-mailer',
            I_EMAIL_X_ORIGINAL_SENDER: 'email-src',
            I_EMAIL_X_ORIGINATING_IP: 'ip-src',
            I_EMAIL_REPLY_TO: 'email-src',
            I_EMAIL_RETURN_PATH: 'email-src',
            I_EMAIL_X_SENDER: 'email-src',
            I_EMAIL_X_SENDER_ID: 'email-src',
            I_EMAIL_X_SENDER_IP: 'ip-src',
            I_FILE_NAME: 'filename',
            I_IP_DEST: 'ip-dst',
            I_IP_SOURCE: 'ip-src',
            I_MD5: 'md5',
            I_SHA1: 'sha1',
            I_SHA256: 'sha256',
            I_URI_PATH: 'uri',
            I_URL: 'url'
        }

        self.misp_url = saq.CONFIG['misp']['url']
        self.api_key = saq.CONFIG['misp']['api_key']
        self._pymisp_client = None

    @property
    def pymisp_client(self):
        if self._pymisp_client is None:
            self._pymisp_client = PyMISP(self.misp_url, self.api_key)

        return self._pymisp_client

    def ace_event_exists_in_tip(self, ace_event_uuid: str) -> bool:
        result = self.pymisp_client.get_event(ace_event_uuid)
        return 'Event' in result

    def add_indicators_to_event_in_tip(self, ace_event_uuid: str, indicators: Union[List[Indicator], List[dict], dict]) -> bool:
        def _convert_indicator_objects_to_dicts(indicator_objects: List[Indicator]) -> List[dict]:
            return [i.json if isinstance(i, Indicator) else i for i in indicator_objects]

        if isinstance(indicators, dict):
            indicators = [indicators]

        indicators = _convert_indicator_objects_to_dicts(indicators)

        misp_event = self.pymisp_client.get_event(ace_event_uuid, pythonify=True)

        for indicator in indicators:
            misp_attribute = MISPAttribute()
            misp_attribute.type = indicator['type']
            misp_attribute.value = indicator['value']

            if 'status' in indicator and indicator['status'].lower() == 'informational':
                misp_attribute.to_ids = False

            if 'tags' in indicator:
                for tag in indicator['tags']:
                    misp_tag = MISPTag()
                    misp_tag.name = tag
                    misp_attribute.tags.append(misp_tag)

            misp_event.attributes.append(misp_attribute)

        result = self.pymisp_client.update_event(misp_event)

        return 'Event' in result

    def create_event_in_tip(self, ace_event_name: str, ace_event_uuid: str, ace_event_url: str) -> bool:
        if self.ace_event_exists_in_tip(ace_event_uuid):
            return True

        event = MISPEvent()
        event.info = ace_event_name
        event.uuid = ace_event_uuid

        link_attribute = MISPAttribute()
        link_attribute.category = 'Internal reference'
        link_attribute.type = 'link'
        link_attribute.value = ace_event_url
        link_attribute.comment = 'ACE Event'
        link_attribute.disable_correlation = True
        event.attributes.append(link_attribute)

        for event_tag in saq.CONFIG['tip']['event_tags'].split(','):
            tag = MISPTag()
            tag.name = event_tag
            event.tags.append(tag)

        result = self.pymisp_client.add_event(event)
        if 'Event' in result:
            logging.info(f'Created MISP event {ace_event_uuid}')
            return True

        return False

    def indicator_exists_in_tip(self, indicator_type: str, indicator_value: str) -> bool:
        result = self.pymisp_client.search('attributes', type_attribute=indicator_type, value=indicator_value)
        return 'Attribute' in result and len(result['Attribute']) >= 1
