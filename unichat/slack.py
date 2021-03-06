# -​*- coding: utf-8 -*​-
import logging
import itertools
import requests

from slackclient import SlackClient


class SlackException(Exception):
    def __init__(self, msg):
        self.msg = msg


class UniChatSlackClient(object):
    def __init__(self, token):
        sc = SlackClient(token)
        logging.info("Connecting to slack...")
        if not sc.rtm_connect():
            raise SlackException("Unable to connect to Slack (invalid token?)")
        logging.info("Connected to slack WebSocket")
        self.token = token
        self.client = sc
        self.my_id = sc.server.login_data[u'self'][u'id']
        users = sc.server.login_data[u'users']
        self.team_members = dict(
            [(user[u'id'], self.__name_tag(user)) for user in users])
        self.related_channels = {}

    def __name_tag(self, user):
        profile = user[u'profile']
        if u'first_name' in profile and u'last_name' in profile:
            return profile[u'first_name'] + " " + profile[u'last_name']
        else:
            return user[u'name']

    def join_channel(self, name):
        c = self.client.server.channels.find(name)
        if c:
            logging.info("Listening on channel: %s" % c.id)
            self.related_channels[name] = c
            return c
        else:
            logging.info("Channel %s not found" % name)
            return None

    def __is_interesting_message(self, event):
        if u'type' not in event or u'user' not in event:
            return False
        if event[u'type'] != 'message':
            return False
        if event[u'user'] == self.my_id:
            return False
        for c in self.related_channels.values():
            if c.id == event[u'channel']:
                return True
        return False

    def get_user_name(self, user_id):
        return self.team_members.get(user_id, "unknown")

    def read_messages_in_channels(self):
        events = self.client.rtm_read()
        return [self.post_process_event(e) for e in events if self.__is_interesting_message(e)]

    def send_message_to_channel(self, channel, message):
        self.client.rtm_send_message(channel, message)

    def send_file_to_channel(self, channel, file_path, title):
        with open(file_path, 'rb') as f:
            response = self.client.api_call('files.upload',
                                            file=f,
                                            title=title,
                                            channels=channel)
            logging.debug("File upload response: %s" % response)
            return response[u'ok']

    def extract_file(self, msg, file_path):
        file_url = msg[u'file'][u'url_private']
        return self.download_file(file_url, file_path)

    def download_file(self, file_url, file_path):
        headers = {"Authorization": "Bearer %s" % self.token}
        r = requests.get(file_url, headers=headers, stream=True)
        if r.status_code == requests.codes.ok:
            with open(file_path, 'wb') as f:
                for block in r.iter_content(1024):
                    f.write(block)
            return True
        else:
            logging.info("failed to download image: %s" % r.status_code)
            return False

    def post_process_event(self, event):
        mentioned_key = u'<@%s>' % self.my_id
        event[u'is_mentioned'] = mentioned_key in event[u'text']
        return event