import os

from peewee import (
    SqliteDatabase,
    Model,
    CharField,
    DateTimeField,
    FloatField,
    CompositeKey,
    ForeignKeyField,
    DateField,
)

DB_DIR = os.path.join(os.environ.get('HOME'), '.zs/data/db')
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DATABASE = SqliteDatabase(os.path.join(DB_DIR, 'assets.db'))


class BaseModel(Model):
    class Meta:
        database = DATABASE


class Deal(BaseModel):

    account = CharField(index=True)
    sub_account = CharField(index=True, null=True)
    time = DateTimeField()
    code = CharField(index=True)
    name = CharField(index=True)
    type = CharField(
        choices=[
            (1, 'transfer_in'),
            (2, 'transfer_out'),
            (3, 'buy'),
            (4, 'sell'),
            (5, 'reinvest'),
            (6, 'bonus'),
            (7, 'spin_off'),
            (8, 'fix_cash'),
        ]
    )
    amount = FloatField()
    price = FloatField()
    money = FloatField()
    fee = FloatField()

    class Meta:
        primary_key = CompositeKey('account', 'time', 'code', 'amount')


class Fund(BaseModel):
    """基金基础信息"""

    code = CharField(primary_key=True)  # 基金代码
    name = CharField(index=True)        # 基金名称
    min_purchace = FloatField()         # 最小申购金额


class FundHistory(BaseModel):
    """基金历史行情"""

    date = DateField(index=True)
    nav = FloatField()          # 单位净值: Net Asset Value
    auv = FloatField(null=True)          # 累计净值: Accumulated Unit Value
    fund = ForeignKeyField(Fund, backref='history')

    class Meta:
        primary_key = CompositeKey('date', 'fund')


class FundBonusHistory(BaseModel):
    """基金分红历史"""

    date = DateField(index=True)
    action = CharField(choices=[(1, 'bonus'), (2, 'spin_off')], index=True)
    value = FloatField()
    fund = ForeignKeyField(Fund, backref='bonus_history')

    class Meta:
        primary_key = CompositeKey('date', 'fund')
