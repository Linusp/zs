import json
import datetime
from logging.config import dictConfig

import click
import requests
from dateutil import tz, parser
from telethon import sync       # noqa

from .telegram import TelegramClient
from .rss.config import RSSConfigManager
from .rss.huginn import generate_kz_scenario, generate_efb_scenario


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


@telegram.command("fetch-msgs")
@click.option("-n", "--name", required=True, help="聊天名称，可为群组、频道、用户名")
@click.option("-d", "--date", default=str(datetime.date.today()))
@click.option("-l", "--limit", type=int, default=100)
@click.option("-o", "--outfile", required=True)
@click.option("-t", "--message-type")
@click.option("-v", "--verbose", is_flag=True)
def fetch_msgs(name, date, limit, outfile, message_type, verbose):
    """获取某个聊天的消息记录"""
    client = TelegramClient()

    start = datetime.datetime.strptime(date, '%Y-%m-%d')
    start = start.replace(tzinfo=tz.tzlocal()).astimezone(datetime.timezone.utc)
    messages = [
        msg.to_dict() for msg in
        client.fetch_messages(name, start=start, limit=limit,
                              msg_type=message_type, verbose=verbose)
    ]
    with open(outfile, 'w') as fout:
        json.dump(messages, fout, ensure_ascii=False, indent=4)


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def rss():
    pass


@rss.command("create-db")
def create_db():
    """创建 RSS 相关的数据库"""
    from .rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

    DATABASE.connect()
    DATABASE.create_tables([WechatArticle, WechatArticleSentHistory])
    DATABASE.close()


@rss.command("list-wx-articles")
@click.option("-n", "--name")
@click.option("-s", "--status",
              type=click.Choice(['sent', 'unsent', 'all']), default='all')
@click.option("-l", "--limit", type=int)
def list_wx_articles(name, status, limit):
    """列出当前获取到的微信公众号文章"""
    from .rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

    DATABASE.connect()
    for article in WechatArticle.search_by_name(name, limit=limit):
        if status == 'all' or \
           (status == 'sent' and WechatArticleSentHistory.is_sent(article.url)) or \
           (status == 'unsent' and not WechatArticleSentHistory.is_sent(article.url)):
            print(f'[{article.date}] {article.name} -- {article.title}')

    DATABASE.close()


@rss.command("fetch-wx-articles")
@click.option("-n", "--name", required=True, help="聊天名称，可为群组、频道、用户名")
@click.option("-d", "--date", default=str(datetime.date.today()))
@click.option("-l", "--limit", type=int, default=100)
@click.option("-v", "--verbose", is_flag=True)
def fetch_wx_articles(name, date, limit, verbose):
    """获取微信公众号文章并写入数据库中"""
    from .rss.models import DATABASE, WechatArticle

    client = TelegramClient()

    start = datetime.datetime.strptime(date, '%Y-%m-%d')
    start = start.replace(tzinfo=tz.tzlocal()).astimezone(datetime.timezone.utc)

    DATABASE.connect()
    created_cnt, processed_cnt = 0, 0
    msgs = client.fetch_messages(name, start=start, limit=limit,
                                 msg_type='wx_article', verbose=verbose)
    for msg in msgs:
        title = msg.content['title']
        url = msg.content['url']
        description = msg.content['desc']
        published_date = msg.timestamp
        name = msg.user
        _, created = WechatArticle.get_or_create(
            name=name, title=title, description=description, url=url, date=published_date
        )

        processed_cnt += 1
        created_cnt += int(created)
        if created:
            print(f"Got new article: {name} -- {title}")

    DATABASE.close()
    print(f"[{datetime.datetime.now()}] Got {created_cnt} new articles")


@rss.command("send-wx-articles")
@click.option("-n", "--name", help="要发送文章所属的微信公众号名称")
@click.option("-l", "--limit", type=int)
@click.option("--send-all", is_flag=True)
def send_wx_articles(name, limit, send_all):
    """将微信公众号发送到 Huginn"""
    from .rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

    config = RSSConfigManager()
    webhooks = config.huginn_webhooks
    if not webhooks:
        click.secho(
            f"`huginn_webhooks` is not found in config file {config.config_file}",
            fg="red", bold=True
        )
        return -1

    DATABASE.connect()
    sent_cnt = 0
    for article in WechatArticle.search_by_name(name, limit):
        if not send_all and WechatArticleSentHistory.is_sent(article.url):
            continue

        webhook_url = webhooks.get(article.name) or webhooks['default']
        if config.proxy:
            response = requests.post(webhook_url, json=article.to_dict(), proxies=config.proxy)
        else:
            response = requests.post(webhook_url, json=article.to_dict())

        if response.status_code == 200:
            click.secho(
                f"[{datetime.datetime.now()}] sent article successfully - name: {article.name}; title: {article.title}",
                fg="green",
            )
            WechatArticleSentHistory.create(url=article.url)
            sent_cnt += 1
        else:
            click.secho(
                f"[{datetime.datetime.now()}] failed to send article: {article.name}; title: {article.title}",
                fg="red",
            )

    click.secho(f"[{datetime.datetime.now()}] sent {sent_cnt} articles", fg='green')
    DATABASE.close()


@rss.command("add-wx-articles")
@click.option("-i", "--infile", required=True)
def add_wx_articles(infile):
    """从 json 文件中添加微信公众号文章和发送记录"""
    from .rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

    DATABASE.connect()
    new_articles_cnt, new_sent = 0, 0
    with open(infile) as f:
        for idx, (_, item) in enumerate(json.load(f).items()):
            _, created = WechatArticle.get_or_create(
                name=item['name'],
                title=item['title'],
                description=item['desc'],
                url=item['url'],
                date=parser.parse(item['date'])
            )
            new_articles_cnt += int(created)

            if item.get('sent') and not WechatArticleSentHistory.is_sent(item['url']):
                WechatArticleSentHistory.create(url=item['url'])
                new_sent += 1

            if created and new_articles_cnt % 100 == 0:
                print(f"[{datetime.datetime.now()}] Got {new_articles_cnt} new articles")

            if new_sent % 100 == 0:
                print(f"[{datetime.datetime.now()}] Got {new_articles_cnt} new sent records")

    DATABASE.close()


@rss.command("gen-scenario")
@click.option("-n", "--name", required=True)
@click.option("-i", "--wxid", required=True)
@click.option("-t", "--scenario-type",
              type=click.Choice(['kz', 'efb']),
              default='efb')
@click.option("--kz-topic-id")
@click.option("--rsshub-base-url", default="https://rsshub.app")
@click.option("-o", "--outfile", required=True)
def gen_scenario(name, wxid, scenario_type, kz_topic_id, rsshub_base_url, outfile):
    """生成用于输出微信公众号 RSS 的 Huginn Scenario"""
    with open(outfile, 'w') as fout:
        scenario = {}
        if scenario_type == 'kz':
            if not kz_topic_id:
                click.secho('Missing option "--kz-topic-id"', fg="red", bold=True)
                return -1
            scenario = generate_kz_scenario(name, wxid, kz_topic_id, rsshub_base_url)
        elif scenario_type == 'efb':
            scenario = generate_efb_scenario(name, wxid)

        json.dump(scenario, fout, ensure_ascii=False, indent=4)
