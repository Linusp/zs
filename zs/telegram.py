import os
import re
import json
import logging
from enum import Enum
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse

import socks
from telethon import sync       # noqa
from telethon.sessions import StringSession
from telethon import TelegramClient as TelethonClient
from telethon.tl.types import Photo, MessageEntityTextUrl

from .consts import CONFIG_DIR, DATA_DIR


LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_FILE = os.path.join(CONFIG_DIR, 'telegram.json')

WX_ARTICLE_PREFIX = '💬👤'
WX_LINK_PREFIX = '🔗'
WX_CHANNEL_PREFIX_PATTERN = re.compile(
    r'(?:^微信)|'
    r'(?:^tele_wechat_bot$)'
)
WX_IMAGE_AUTHOR_PAT = re.compile(r'^(?P<name>.+):\nsent a picture\.$')


class TelegramConfigManager():

    DEFAULT_DOWNLOAD_PATH = os.path.join(DATA_DIR, 'telegram')

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
    def api_id(self):
        return self.data.get('api_id')

    @api_id.setter
    def api_id(self, value):
        self.data['api_id'] = value

    @property
    def api_hash(self):
        return self.data.get('api_hash')

    @api_hash.setter
    def api_hash(self, value):
        self.data['api_hash'] = value

    @property
    def session(self):
        return self.data.get('session')

    @session.setter
    def session(self, value):
        self.data['session'] = value

    @property
    def proxy(self):
        return self.data.get('proxy')

    @property
    def download_path(self):
        download_path = self.data.get("download_path", self.DEFAULT_DOWNLOAD_PATH)
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        return download_path

    @property
    def user(self):
        return self.data.get('user')


def get_proxy_from_uri(uri):
    if not uri:
        return None

    if uri.startswith('http://') or uri.startswith('https://'):
        address, *remain = re.sub(r'^https?://', '', uri).split(':')
        port = 80 if len(remain) != 1 else int(remain[0])
        return socks.HTTP, address, port

    if uri.startswith('socks://'):
        address, *remain = re.sub(r'^socks://', '', uri).split(':')
        port = 80 if len(remain) != 1 else int(remain[0])
        return socks.SOCKS5, address, port

    return None


class MessageType(Enum):

    TEXT = 1000                    # 文本
    IMAGE = 1001                   # 图片
    MULTI = 1002                   # 图文混合
    WX_TEXT = 2000                 # 微信用户消息
    WX_IMAGE = 2001                # 微信图片消息
    WX_ARTICLE = 2002              # 微信公众号文章
    OTHER = 3000                   # 除上述六种类型外的

    @staticmethod
    def from_str(type_name):
        type_map = {
            'text': MessageType.TEXT,
            'image': MessageType.IMAGE,
            'multi': MessageType.MULTI,
            'wx_text': MessageType.WX_TEXT,
            'wx_image': MessageType.WX_IMAGE,
            'wx_article': MessageType.WX_ARTICLE,
            'other': MessageType.OTHER,
        }
        if type_name in type_map:
            return type_map[type_name]

        raise ValueError('Invalid type name %s' % type_name)


class Message():

    WX_MSG_TYPES = (MessageType.WX_TEXT, MessageType.WX_IMAGE, MessageType.WX_ARTICLE)
    IMG_MSG_TYPES = (MessageType.IMAGE, MessageType.WX_IMAGE, MessageType.MULTI)

    def __init__(self, id, type, content, timestamp, user, reply_to, origin=None):
        assert isinstance(type, MessageType)
        if type == MessageType.MULTI:
            assert isinstance(content, list)
        elif type == MessageType.WX_ARTICLE:
            assert isinstance(content, dict)
        else:
            assert isinstance(content, str)

        self.id = id
        self.type = type
        self.content = content
        self.timestamp = timestamp
        self.user = user
        self.reply_to = reply_to
        self.origin = origin

    @staticmethod
    def get_chat_name(message):
        chat_name = ''
        if hasattr(message.chat, 'title'):
            chat_name = message.chat.title
        elif hasattr(message.chat, 'username'):
            chat_name = message.chat.username
            if not chat_name:
                chat_name = message.chat.first_name

        return chat_name

    @staticmethod
    def get_message_type(message):
        chat_name = Message.get_chat_name(message)
        if WX_CHANNEL_PREFIX_PATTERN.match(chat_name):
            return Message.get_wx_message_type(message)

        if isinstance(message.photo, Photo) and message.photo.sizes and \
           not message.entities:
            if not message.text:
                return MessageType.IMAGE
            else:
                return MessageType.MULTI

        if message.text:
            if message.entities:
                return MessageType.TEXT
            elif not message.media:
                return MessageType.TEXT
            else:
                return MessageType.OTHER

        # FIXME: sticker 会被当作 OTHER，然后在后面的解析里会得不到结果
        return MessageType.OTHER

    @staticmethod
    def get_wx_message_type(message):
        if message.entities and len(message.entities) == 2 and \
           isinstance(message.entities[1], MessageEntityTextUrl):
            return MessageType.WX_ARTICLE

        if message.media and not message.entities:
            if isinstance(message.photo, Photo):
                return MessageType.WX_IMAGE
        else:
            return MessageType.WX_TEXT

        return MessageType.OTHER

    @classmethod
    def parse_wx_text_message(cls, message):
        # FIXME: 未考虑引用的情况
        user = 'unknown'
        if message.raw_text.find('\n') >= 0:
            user, content = message.raw_text.split('\n', maxsplit=1)
        else:
            matches = WX_GENERAL_AUTHOR_PAT.match(message.raw_text)
            if matches:
                user = matches.groupdict()['name'].strip()
                content = message.raw_text.replace(user, '', 1).strip().strip(':')
            else:
                content = message.raw_text

        user = user.replace(WX_ARTICLE_PREFIX, '').strip(': ')
        content = content.strip(WX_LINK_PREFIX).strip()
        msg_type = MessageType.WX_TEXT
        return cls(message.id, msg_type, content, message.date, user, None, message)

    @classmethod
    def parse_wx_article(cls, message):
        msg_text = message.raw_text.strip()
        name, title, *desc = msg_text.split('\n')

        name = name.replace(WX_ARTICLE_PREFIX, '').strip(' :')
        title = title.replace(WX_LINK_PREFIX, '').strip()

        url = message.entities[1].url
        url_info = urlparse(url)
        parameters = dict(parse_qsl(url_info.query))
        new_query = urlencode({
            k: v for k, v in parameters.items()
            if k in ('__biz', 'mid', 'idx', 'sn')
        })
        url = 'http://mp.weixin.qq.com/s?' + new_query

        content = {
            'title': title,
            'desc': '\n'.join(desc),
            'url': url,
            'date': str(message.date),
        }

        msg_type = MessageType.WX_ARTICLE
        return cls(message.id, msg_type, content, message.date, name, None, message)

    @classmethod
    def parse_wx_message(cls, message, msg_type, config=None, wx_msg_index=None):
        if msg_type == MessageType.WX_TEXT:
            # FIXME: 未使用 wx_msg_index 参数
            return cls.parse_wx_text_message(message)
        if msg_type == MessageType.WX_ARTICLE:
            return cls.parse_wx_article(message)
        if msg_type == MessageType.WX_IMAGE:
            if config:
                download_path = config.download_path
            else:
                download_path = TelegramConfigManager.DEFAULT_DOWNLOAD_PATH

            if hasattr(message.chat, 'username'):
                chat_name = message.chat.username
            else:
                chat_name = message.chat.title

            content = os.path.join(download_path, f'{chat_name}_{message.id}.jpg')

            if not message.text or message.text.strip() == 'You:':
                user = 'You'
                if config and config.user:
                    user = config.user
            else:
                try:
                    user = WX_IMAGE_AUTHOR_PAT.match(message.text).groupdict()['name']
                except Exception:
                    user = 'unknown'

            return cls(message.id, msg_type, content, message.date, user, None, message)

        raise NotImplementedError

    @classmethod
    def parse(cls, message, msg_type=None, config=None, wx_msg_index=None):
        msg_type = msg_type or cls.get_message_type(message) or MessageType.OTHER
        if msg_type in cls.WX_MSG_TYPES:
            return cls.parse_wx_message(message, msg_type, config, wx_msg_index)

        content = None
        chat_name = cls.get_chat_name(message)
        if msg_type in (MessageType.TEXT, MessageType.OTHER):
            content = message.raw_text or ''
        elif msg_type in (MessageType.IMAGE, MessageType.MULTI):
            if config:
                download_path = config.download_path
            else:
                download_path = TelegramConfigManager.DEFAULT_DOWNLOAD_PATH

            content = os.path.join(download_path,
                                   f'{chat_name}_{message.id}.jpg')
            if msg_type == MessageType.MULTI:
                content = [
                    {
                        'type': MessageType.IMAGE,
                        'content': content,
                    },
                    {
                        'type': MessageType.TEXT,
                        'content': message.raw_text,
                    }
                ]

        if message.from_id:
            user = message.client.get_entity(message.from_id).username
        else:
            user = chat_name
        return cls(message.id, msg_type, content, message.date,
                   user, message.reply_to_msg_id, message)

    def to_dict(self):
        data = {
            'id': self.id,
            'type': self.type.value,
            'content': self.content,
            'timestamp': str(self.timestamp),
            'user': self.user,
            'reply_to': self.reply_to,
        }
        if self.type == MessageType.MULTI:
            for item in data['content']:
                item['type'] = item['type'].value
        return data


class TelegramClient():

    IGNORED_MSG_PATTERNS = [
        re.compile(r'WeChat Slave'),
        re.compile(r'tele_wechat_bot'),
        re.compile(r'^/'),
        re.compile(r'System'),
    ]

    def __init__(self, config_manager=None):
        config_manager = config_manager or TelegramConfigManager()
        if not config_manager.api_id or not config_manager.api_hash:
            api_id, api_hash = self.ask_base_info()
            config_manager.api_id = api_id
            config_manager.api_hash = api_hash
            config_manager.save()

        api_id, api_hash = config_manager.api_id, config_manager.api_hash
        proxy = get_proxy_from_uri(config_manager.proxy)
        if not config_manager.session:
            session = StringSession()
            with TelethonClient(session, api_id, api_hash, proxy=proxy) as client:
                config_manager.session = client.session.save()
                config_manager.save()

        # sync 模式下这里要加一个 start()，去掉的话会触发 ConnectionError 异常
        self.client = TelethonClient(StringSession(config_manager.session),
                                     config_manager.api_id,
                                     config_manager.api_hash,
                                     proxy=proxy).start()
        self.config_manager = config_manager

    @staticmethod
    def ask_base_info():
        print('Create your application on `https://my.telegram.org`, '
              'then enter api_id and api_hash below:')
        api_id = input('App api_id').strip()
        api_hash = input('App api_hash').strip()
        return api_id, api_hash

    @lru_cache()
    def get_dialog(self, name):
        for dialog in self.client.get_dialogs():
            if dialog.name == name:
                return dialog

        return None

    def fetch_messages(self, name, start=None, batch=100, limit=None, msg_type=None):
        """获取某个频道或群组的聊天记录

        Parameters
        ----------
        name: str
            要获取的频道或群组的名字
        start: datetime
            消息的起始时间，早于该时间的消息将会被忽略，默认不设置取所有消息
        batch: int
            获取消息时为减少网络开销，将会一批一批获取，该参数用于设置每个批次的
            最大消息数量，默认设置为 100
        limit: int
            获取的最大消息数量，默认不设置，当设置时，若 start 未设置则只取最近的
            limit 条消息
        msg_type: str
            消息类型，可选 'text', 'image' 两类，默认不设置获取所有类型
            的消息

        Return
        ------
        results: list of Message
        """
        dialog = self.get_dialog(name)
        if not dialog:
            return []

        results, cnt = [], 0
        batch_size = batch if not limit else min(limit, batch)
        last_offset_id, offset_id = None, None
        while True:
            if offset_id:
                message_packages = self.client.iter_messages(
                    dialog.entity,
                    limit=batch_size,
                    offset_id=offset_id
                )
                last_offset_id = offset_id
            else:
                message_packages = self.client.iter_messages(
                    dialog.entity,
                    limit=batch_size,
                )

            msg_timestamp = None
            for message in message_packages:
                if cnt > 0:
                    LOGGER.info("processed %d messages and got %d valid messages",
                                cnt, len(results))

                cnt += 1
                if isinstance(message.raw_text, str) and \
                   any(pat.findall(message.raw_text) for pat in self.IGNORED_MSG_PATTERNS):
                    continue

                offset_id = message.id
                msg = Message.parse(message, config=self.config_manager)
                msg_timestamp = message.date
                if not msg.content:
                    continue

                if start and msg.timestamp < start:
                    break

                if not msg_type or msg.type == MessageType.from_str(msg_type):
                    results.append(msg)
                    if msg.type in Message.IMG_MSG_TYPES:
                        self.download_photo(msg)

                if limit and len(results) >= limit:
                    break

            if start and msg_timestamp and msg_timestamp < start:
                break

            if limit and len(results) >= limit:
                break

            if offset_id == last_offset_id:
                break

        return results[::-1]

    def download_photo(self, message):
        photo = None
        if isinstance(message.content, str):
            photo = message.content
        elif isinstance(message.content, list):
            if message.content[0]['type'] == MessageType.IMAGE:
                photo = message.content[0]['content']

        if not photo or os.path.exists(photo):
            return

        download_path = os.path.dirname(photo)
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        message.origin.download_media(photo)
        LOGGER.info("download image file: %s", photo)
