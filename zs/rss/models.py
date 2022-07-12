import datetime
import os

from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    Model,
    SqliteDatabase,
    TextField,
)

DB_DIR = os.path.join(os.environ.get("HOME"), ".zs/data/db")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DATABASE = SqliteDatabase(os.path.join(DB_DIR, "rss.db"))


class BaseModel(Model):
    class Meta:
        database = DATABASE


class WechatArticle(BaseModel):

    """存储微信公众号文章的基本信息"""

    name = CharField(index=True)
    title = CharField(index=True)
    description = CharField()
    url = CharField(unique=True, index=True)
    date = DateTimeField()

    @classmethod
    def search_by_name(cls, name=None, limit=None):
        search = cls.select()
        if name:
            search = search.where(cls.name == name)

        if limit:
            search = search.order_by(cls.date.desc()).limit(limit)
            items = sorted(search, key=lambda item: item.date)
            return items

        search = search.order_by(cls.date)
        return search

    def to_dict(self):
        return {
            "name": self.name,
            "title": self.title,
            "desc": self.description,
            "url": self.url,
            "date": str(self.date),
        }


class WechatArticleSentHistory(BaseModel):
    """记录微信公众号文章的发送历史"""

    id = AutoField()
    url = CharField(index=True)
    date = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def is_sent(cls, url):
        return bool(cls.select().where(cls.url == url))


class Feed(BaseModel):
    """记录通用的 RSS 订阅源数据"""

    name = CharField(index=True, unique=True)
    title = CharField(index=True)
    subtitle = CharField()
    link = CharField(index=True)
    feed_link = CharField(index=True, unique=True)
    version = CharField(index=True)


class Article(BaseModel):
    """记录通用 RSS 条目数据"""

    feed = ForeignKeyField(Feed, backref="articles")
    title = CharField(index=True)
    summary = TextField()
    link = CharField(index=True, unique=True)
    publish_date = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def search_by_feed(cls, feed_name, limit=None):
        feed = Feed.get_or_none(Feed.name == feed_name)
        if feed:
            search = cls.select().where(cls.feed == feed)
        else:
            search = cls.select()

        if limit:
            search = search.order_by(cls.publish_date.desc()).limit(limit)
            items = sorted(search, key=lambda item: item.publish_date)
            return items

        return search


class SentHistory(BaseModel):
    """记录文章发送记录"""

    url = CharField(index=True)
    date = DateTimeField(default=datetime.datetime.now)
    dest = CharField(index=True)

    @classmethod
    def is_sent(cls, url, dest=None):
        if not dest:
            return bool(cls.select().where(cls.url == url))

        return bool(cls.select().where(cls.url == url).where(cls.dest == dest))
