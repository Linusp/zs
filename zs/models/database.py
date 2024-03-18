import logging
import os

from peewee import DatabaseProxy, Model, MySQLDatabase, SqliteDatabase
from playhouse.shortcuts import ReconnectMixin

LOGGER = logging.getLogger(__name__)
DATABASE_PROXY = DatabaseProxy()

DB_DIR = os.path.join(os.environ.get("HOME"), ".zs/data/db")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DEFAULT_DB_CONFIG = {'type': 'sqlite', 'db_file': os.path.join(DB_DIR, 'zs.db')}


class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    pass


def init_database(config=None):
    config = config or DEFAULT_DB_CONFIG
    database = None
    database_type = config.get('type', 'mysql')
    if database_type == 'sqlite' and config:
        db_file = os.path.abspath(os.path.expanduser(config['db_file']))
        db_dir = os.path.dirname(db_file)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        database = SqliteDatabase(db_file)
    elif database_type == 'mysql' and config:
        database = ReconnectMySQLDatabase(
            config['database'],
            host=config['host'],
            port=int(config.get('port', 3306)),
            user=config['user'],
            password=config['password'],
        )

    if database is not None:
        DATABASE_PROXY.initialize(database)
        LOGGER.info("Initialized database successfully")
        return

    LOGGER.warning("Failed to initialize database")


init_database()


class BaseModel(Model):
    class Meta:
        database = DATABASE_PROXY
