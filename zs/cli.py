import json
import datetime
from logging.config import dictConfig

import click
from dateutil import tz
from telethon import sync       # noqa

from .telegram import TelegramClient


dictConfig({
    'version': 1,
    'formatters': {
        'simple': {
            'format': '%(asctime)s - %(filename)s:%(lineno)s: %(message)s',
        }
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            "stream": "ext://sys.stdout",
        },
    },
    'loggers': {
        '__main__': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True
        },
        'zs': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
})


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def telegram():
    pass


@telegram.command()
@click.option("-n", "--name", required=True, help="聊天名称，可为群组、频道、用户名")
@click.option("-d", "--date", default=str(datetime.date.today()))
@click.option("-l", "--limit", type=int, default=100)
@click.option("-o", "--outfile", required=True)
@click.option("-t", "--message-type")
def fetch_msgs(name, date, limit, outfile, message_type):
    """获取某个聊天的消息记录"""
    client = TelegramClient()

    start = datetime.datetime.strptime(date, '%Y-%m-%d')
    start = start.replace(tzinfo=tz.tzlocal()).astimezone(datetime.timezone.utc)
    messages = [
        msg.to_dict() for msg in
        client.fetch_messages(name, start=start, limit=limit, msg_type=message_type)
    ]
    with open(outfile, 'w') as fout:
        json.dump(messages, fout, ensure_ascii=False, indent=4)
