import os
import datetime

from peewee import (
    SqliteDatabase,
    Model,
    CharField,
    DateTimeField,
    AutoField,
)

DB_DIR = os.path.join(os.environ.get('HOME'), '.zs/data/db')
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DATABASE = SqliteDatabase(os.path.join(DB_DIR, 'rss.db'))


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
        if name:
            search = cls.select().where(cls.name == name)
        else:
            search = cls.select().order_by(cls.date)

        if limit:
            search = search.order_by(cls.date.desc()).limit(limit)

        search = search.order_by(cls.date)
        return search

    def to_dict(self):
        return {
            'name': self.name,
            'title': self.title,
            'desc': self.description,
            'url': self.url,
            'date': str(self.date),
        }


class WechatArticleSentHistory(BaseModel):

    """记录微信公众号文章的发送历史"""

    id = AutoField()
    url = CharField(index=True)
    date = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def is_sent(cls, url):
        return bool(cls.select().where(cls.url == url))
