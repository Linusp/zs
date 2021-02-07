import os
import json

from ..consts import CONFIG_DIR


DEFAULT_CONFIG_FILE = os.path.join(CONFIG_DIR, 'rss.json')


class RSSConfigManager():

    def __init__(self, config_file=DEFAULT_CONFIG_FILE):
        self.config_file = config_file
        self.data = {}
        if os.path.exists(config_file):
            with open(self.config_file) as f:
                self.data = json.load(f)

    def save(self):
        config_dir = os.path.dirname(self.config_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    @property
    def huginn_webhooks(self):
        return self.data.get('huginn_webhooks', {})

    @property
    def proxy(self):
        return self.data.get('proxy')

    @property
    def senders(self):
        return self.data.get('senders', {})
