import json
import datetime
from logging.config import dictConfig
from time import mktime

import click
import requests
from dateutil import tz, parser
from telethon import sync       # noqa
import feedparser
from tabulate import tabulate

from zs.telegram import TelegramClient
from zs.rss.config import RSSConfigManager
from zs.rss.huginn import (
    generate_kz_scenario,
    generate_efb_scenario,
    generate_daily_digest_scenario,
)

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
def main():
    pass


@main.command("create-db")
def create_db():
    """创建 RSS 相关的数据库"""
    from zs.rss.models import (
        DATABASE,
        WechatArticle,
        WechatArticleSentHistory,
        Feed,
        Article,
        SentHistory,
    )

    DATABASE.connect()
    DATABASE.create_tables([
        WechatArticle,
        WechatArticleSentHistory,
        Feed,
        Article,
        SentHistory,
    ])
    DATABASE.close()


@main.command("list-wx-articles")
@click.option("-n", "--name")
@click.option("-s", "--status",
              type=click.Choice(['sent', 'unsent', 'all']), default='all')
@click.option("-l", "--limit", type=int)
def list_wx_articles(name, status, limit):
    """列出当前获取到的微信公众号文章"""
    from zs.rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

    DATABASE.connect()
    for article in WechatArticle.search_by_name(name, limit=limit):
        if status == 'all' or \
           (status == 'sent' and WechatArticleSentHistory.is_sent(article.url)) or \
           (status == 'unsent' and not WechatArticleSentHistory.is_sent(article.url)):
            print(f'[{article.date}] {article.name} -- {article.title}')

    DATABASE.close()


@main.command("fetch-wx-articles")
@click.option("-n", "--name", required=True, help="聊天名称，可为群组、频道、用户名")
@click.option("-d", "--date", default=str(datetime.date.today()))
@click.option("-l", "--limit", type=int, default=100)
@click.option("-v", "--verbose", is_flag=True)
def fetch_wx_articles(name, date, limit, verbose):
    """获取微信公众号文章并写入数据库中"""
    from zs.rss.models import DATABASE, WechatArticle

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


@main.command("send-wx-articles")
@click.option("-n", "--name", help="要发送文章所属的微信公众号名称")
@click.option("-l", "--limit", type=int)
@click.option("--send-all", is_flag=True)
def send_wx_articles(name, limit, send_all):
    """将微信公众号发送到 Huginn"""
    from zs.rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

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

        webhook_url = webhooks.get(article.name) or webhooks.get('default')
        if not webhook_url:
            continue

        if config.proxy:
            response = requests.post(webhook_url, json=article.to_dict(), proxies=config.proxy)
        else:
            response = requests.post(webhook_url, json=article.to_dict())

        if not response:
            continue
        if response.status_code in (200, 201):
            click.secho(
                f"[{datetime.datetime.now()}] sent article successfully - "
                f"name: {article.name}; title: {article.title}",
                fg="green",
            )
            WechatArticleSentHistory.create(url=article.url)
            sent_cnt += 1
        else:
            click.secho(
                f"[{datetime.datetime.now()}] failed to send article:"
                f" {article.name}; title: {article.title}",
                fg="red",
            )

    click.secho(f"[{datetime.datetime.now()}] sent {sent_cnt} articles", fg='green')
    DATABASE.close()


@main.command("add-wx-articles")
@click.option("-n", "--name")
@click.option("-i", "--infile", required=True)
def add_wx_articles(name, infile):
    """从 json 文件中添加微信公众号文章和发送记录"""
    from zs.rss.models import DATABASE, WechatArticle, WechatArticleSentHistory

    DATABASE.connect()
    new_articles_cnt, new_sent = 0, 0
    with open(infile) as f:
        for idx, (_, item) in enumerate(json.load(f).items()):
            if name and item['name'] != name:
                continue

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


@main.command("gen-wx-scenario")
@click.option("-n", "--name", required=True)
@click.option("-i", "--wxid", required=True)
@click.option("-t", "--scenario-type",
              type=click.Choice(['kz', 'efb']),
              default='efb')
@click.option("--kz-topic-id")
@click.option("--rsshub-base-url", default="https://rsshub.app")
@click.option("-o", "--outfile", required=True)
def gen_wx_scenario(name, wxid, scenario_type, kz_topic_id, rsshub_base_url, outfile):
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


@main.command("gen-daily-scenario")
@click.option("--feed-url", required=True)
@click.option("-n", "--name")
@click.option("-d", "--description")
@click.option("-o", "--outfile", required=True)
def gen_daily_scenario(feed_url, name, description, outfile):
    """为一个指定的 RSS 生成每日摘要 RSS"""
    with open(outfile, 'w') as fout:
        scenario = generate_daily_digest_scenario(feed_url, name, description)
        json.dump(scenario, fout, ensure_ascii=False, indent=4)


@main.command("add-feed")
@click.option("-n", "--name", required=True)
@click.option("-f", "--feed-url", required=True)
def add_feed(name, feed_url):
    """添加 RSS Feed 到数据库"""
    from zs.rss.models import Feed

    if Feed.get_or_none(Feed.feed_link == feed_url):
        click.secho("this feed is already in databse", fg='red')
    else:
        feed_data = feedparser.parse(feed_url)
        feed_info = feed_data['feed']
        Feed.get_or_create(
            name=name,
            title=feed_info['title'],
            subtitle=feed_info.get('subtitle', ''),
            link=feed_info['link'],
            feed_link=feed_url,
            version=feed_data['version'],
        )
        click.secho("added this feed to database", fg='green')


@main.command("list-feeds")
def list_feeds():
    """列出当前的 RSS Feed"""
    from zs.rss.models import Feed

    data = []
    for feed in Feed.select():
        data.append([feed.name, feed.feed_link])

    print(
        tabulate(data,
                 headers=['name', 'url'],
                 showindex='always',
                 tablefmt='pretty')
    )


@main.command("fetch-rss")
@click.option("-n", "--name", required=True, help="feed 名字")
def fetch_rss_articles(name):
    """获取 RSS 并写入数据库中"""
    from zs.rss.models import Feed, Article

    feed = Feed.get_or_none(Feed.name == name)
    if not feed:
        click.secho(f"Feed is not found: {name}", fg='red')
        return -1

    feed_url = feed.feed_link
    feed_data = feedparser.parse(feed_url)
    created_cnt = 0
    for entry in feed_data['entries']:
        publish_date = None
        if entry.get('published_parsed'):
            publish_date = datetime.datetime.fromtimestamp(mktime(entry.get('published_parsed')))
        else:
            publish_date = datetime.datetime.now()

        query = Article.select().where(Article.link == entry['link'])
        if not query.exists():
            Article.create(
                title=entry['title'],
                link=entry['link'],
                summary=entry.get('summary') or entry.get('content') or '',
                feed=feed,
                publish_date=publish_date,
            )
            created_cnt += 1

    click.secho(f"fetched {created_cnt} new articles")


@main.command("list-articles")
@click.option("-n", "--name")
@click.option("-s", "--status",
              type=click.Choice(['sent', 'unsent', 'all']), default='all')
@click.option("-d", "--sent-dest")
@click.option("-l", "--limit", type=int)
def list_articles(name, status, sent_dest, limit):
    """列出当前获取到的微信公众号文章"""
    from zs.rss.models import Article, SentHistory

    for article in Article.search_by_feed(name, limit=limit):
        if status == 'all' or \
           (status == 'sent' and SentHistory.is_sent(article.url, dest=sent_dest)) or \
           (status == 'unsent' and not SentHistory.is_sent(article.url)):
            title = article.title if len(article.title) <= 30 else article.title[:30] + '...'
            print(f'[{article.publish_date}] {article.feed.name} -- {title}')


@main.command("send-articles")
@click.option("-n", "--name", help="要发送文章的订阅源的名字", required=True)
@click.option("-l", "--limit", type=int)
@click.option("--dest-type", required=True)
@click.option("--send-all", is_flag=True)
def send_articles(name, limit, dest_type, send_all):
    from zs.rss.models import Article, SentHistory
    from zs.rss.sender import get_sender_cls

    sent_cnt = 0

    sender_cls = get_sender_cls(dest_type)
    if sender_cls is None:
        click.secho("cannot support your dest url now", fg='red')
        return -1

    config = RSSConfigManager()
    sender_config = config.senders.get(name, {}).get(dest_type, {})
    if not sender_config:
        click.secho(
            f"[{datetime.datetime.now()}] sender config is missing in `{config.config_file}`",
            fg='red',
        )
        return -1

    sender = sender_cls(**sender_config)
    for article in Article.search_by_feed(name, limit):
        if not send_all and SentHistory.is_sent(article.link, dest_type):
            continue

        response = sender.send(article)
        if not response:
            continue
        if response.status_code in (200, 201):
            click.secho(
                f"[{datetime.datetime.now()}] sent article successfully - "
                f"name: {article.feed.name}; title: {article.title}",
                fg="green",
            )
            SentHistory.create(url=article.link, dest=dest_type)
            sent_cnt += 1
        else:
            click.secho(
                f"[{datetime.datetime.now()}] failed to send article:"
                f" {article.feed.name}; title: {article.title}",
                fg="red",
            )

    click.secho(f"[{datetime.datetime.now()}] sent {sent_cnt} articles", fg='green')
