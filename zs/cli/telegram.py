import datetime
import json
from logging.config import dictConfig

import click
from dateutil import tz
from telethon import sync  # noqa

from zs.telegram import TelegramClient

dictConfig(
    {
        "version": 1,
        "formatters": {
            "simple": {
                "format": "%(asctime)s - %(filename)s:%(lineno)s: %(message)s",
            }
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "__main__": {"handlers": ["default"], "level": "DEBUG", "propagate": True},
            "zs": {"handlers": ["default"], "level": "DEBUG", "propagate": True},
        },
    }
)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


@main.command("fetch-msgs")
@click.option("-n", "--name", required=True, help="聊天名称，可为群组、频道、用户名")
@click.option("--begin-date", default=str(datetime.date.today()))
@click.option("--end-date", default=str(datetime.date.today() + datetime.timedelta(days=1)))
@click.option("--offset-id", type=int)
@click.option("-l", "--limit", type=int, default=100)
@click.option("-o", "--outfile", required=True)
@click.option("-t", "--message-type")
@click.option("-v", "--verbose", is_flag=True)
def fetch_msgs(name, begin_date, end_date, offset_id, limit, outfile, message_type, verbose):
    """获取某个聊天的消息记录"""
    client = TelegramClient()

    start = datetime.datetime.strptime(begin_date, "%Y-%m-%d")
    start = start.replace(tzinfo=tz.tzlocal()).astimezone(datetime.timezone.utc)

    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    end = end.replace(tzinfo=tz.tzlocal()).astimezone(datetime.timezone.utc)

    messages = [
        msg.to_dict()
        for msg in client.fetch_messages(
            name,
            start=start,
            end=end,
            limit=limit,
            offset_id=offset_id,
            msg_type=message_type,
            verbose=verbose,
        )
    ]
    with open(outfile, "w") as fout:
        json.dump(messages, fout, ensure_ascii=False, indent=4)
