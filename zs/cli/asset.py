import re
import csv
import json
from datetime import datetime, timedelta
import logging
from operator import itemgetter
from logging.config import dictConfig
from collections import defaultdict

import click
from tabulate import tabulate

from zs.asset.data import QiemanExporter, EastMoneyFundExporter
from zs.asset.models import (
    DATABASE,
    Deal,
    Fund,
    FundHistory,
    FundBonusHistory,
)

LOGGER = logging.getLogger(__name__)
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


@main.command("export-qieman")
@click.option("-c", "--config-file", required=True)
@click.option("--asset-id", required=True)
@click.option("-o", "--outfile", required=True)
def export_qieman_orders(config_file, asset_id, outfile):
    """导出且慢订单记录"""
    with open(config_file) as f:
        config = json.load(f)
        exporter = QiemanExporter(**config)
        orders = exporter.list_orders(asset_id)

    with open(outfile, 'w') as fout:
        for order in orders:
            line = json.dumps(order, ensure_ascii=False, sort_keys=True)
            print(line, file=fout)


@main.command("parse-qieman")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
@click.option("--add-transfer", is_flag=True, help="是否在买入时自动产生一笔等额资金转入")
def parse_qieman_orders(infile, outfile, add_transfer):
    """解析且慢订单记录为 csv 格式"""
    results = []
    with open(infile) as fin:
        pattern = re.compile(r'再投资份额(\d+\.\d+)份')
        unknown_buyings, transfer_in = [], defaultdict(float)
        for line in fin:
            item = json.loads(line)
            account = item['umaName']
            sub_account = item['capitalAccountName']
            if item['capitalAccountName'] == '货币三佳':
                pass
            elif item['hasDetail']:
                if item['orderStatus'] != 'SUCCESS':
                    continue

                for order in item['compositionOrders']:
                    value = order['nav']
                    fee = order['fee']
                    order_time = datetime.fromtimestamp(order['acceptTime'] / 1000)
                    count = order['uiShare']
                    money = order['uiAmount']
                    action = 'unknown'
                    if order['payStatus'] == '2':
                        action = 'buy'
                    elif order['payStatus'] == '0':
                        action = 'sell'

                    fund_code = order['fund']['fundCode']
                    fund_name = order['fund']['fundName']
                    if fund_name.find('广发钱袋子') >= 0:  # FIXME: 应当用基金类型来判断
                        continue

                    if 'destFund' in order:
                        money -= fee
                        unknown_buyings.append([
                            account, sub_account, order_time,
                            order['destFund']['fundCode'], order['destFund']['fundName'],
                            money
                        ])
                    elif add_transfer and action == 'buy':
                        transfer_in[(account, str(order_time.date()))] += money

                    results.append([
                        account, sub_account, order_time, fund_code, fund_name,
                        action, count, value, money, fee
                    ])
            elif item['uiOrderDesc'].find('再投资') >= 0:
                fee = 0
                order_time = datetime.fromtimestamp(item['acceptTime'] / 1000)
                count = float(pattern.findall(item['uiOrderDesc'])[0])
                money = item['uiAmount']
                value = round(float(money) / float(count), 4)
                action = 'reinvest'
                fund_code = item['fund']['fundCode']
                fund_name = item['fund']['fundName']
                # 且慢交易记录里红利再投资日期是再投资到账日期，不是实际发生的日期，
                # 这里尝试根据净值往前查找得到真正的日期
                fund = Fund.get_or_none(code=fund_code)
                if fund:
                    search = fund.history.where(FundHistory.date < order_time.date())
                    search = search.where(
                        FundHistory.date >= order_time.date() - timedelta(days=10)
                    )
                    search = search.order_by(FundHistory.date.desc())
                    candidates = []
                    for record in search[:3]:
                        candidates.append((record, abs(record.nav - value)))

                    record, nav_diff = min(candidates, key=itemgetter(1))
                    LOGGER.info(
                        "correct reinvestment time of `%s` from `%s` to `%s`(nav diff: %f)",
                        fund_code, order_time, record.date, nav_diff
                    )
                    value = record.nav
                    order_time = datetime.strptime(f'{record.date} 08:00:00', '%Y-%m-%d %H:%M:%S')
                else:
                    LOGGER.warning(
                        "can not guess real order time of reinvestment(code: %s;time: %s; nav: %s)",
                        fund_code, order_time, value
                    )

                results.append([
                    account, sub_account, order_time, fund_code, fund_name,
                    action, count, value, money, fee
                ])
            elif item['uiOrderCodeName'].find('现金分红') >= 0:
                order_time = datetime.fromtimestamp(item['acceptTime'] / 1000)
                results.append([
                    account, sub_account, order_time,
                    item['fund']['fundCode'], item['fund']['fundName'],
                    'bonus', item['uiAmount'], 1.0, item['uiAmount'], 0.0
                ])

        for (account, date), money in transfer_in.items():
            order_time = datetime.strptime(f'{date} 08:00:00', '%Y-%m-%d %H:%M:%S')
            results.append([
                account, '', order_time, 'CASH', '现金',
                'transfer_in', money, 1.0, money, 0.0
            ])

        for account, sub_account, order_time, code, name, money in unknown_buyings:
            fund = Fund.get_or_none(code=code)
            if not fund:
                LOGGER.warning(
                    "fund `%s` is not found in database, add it with `update-fund`",
                    code
                )
                continue

            close_time = datetime.strptime(f'{order_time.date()} 15:00:00', '%Y-%m-%d %H:%M:%S')
            if order_time > close_time:
                history_date = order_time.replace(days=1).date()
            else:
                history_date = order_time.date()

            history_records = list(fund.history.where(FundHistory.date == history_date))
            if not history_records:
                LOGGER.warning(
                    "history data of fund `%s` is not found in database, try `update-fund`",
                    code
                )
                continue

            value = history_records[0].nav
            count = round(money / value, 2)
            results.append([
                account, sub_account, order_time, code, name,
                'buy', count, value, money, 0.0
            ])

    results.sort(key=itemgetter(2, 0, 1, 3, 5))
    with open(outfile, 'w') as fout:
        for row in results:
            print(
                f'{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}\t{row[4]}\t{row[5]}\t'
                f'{row[6]:.4f}\t{row[7]:.4f}\t{row[8]:.4f}\t{row[9]:.4f}',
                file=fout
            )


@main.command("parse-pingan")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
def parse_pingan(infile, outfile):
    """解析平安证券的交易记录"""
    action_mappings = {
        '证券买入': 'buy',
        '证券卖出': 'sell',
        '银证转入': 'transfer_in',
        '银证转出': 'transfer_out',
        '利息归本': 'reinvest',
    }
    results = []
    with open(infile) as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            if row['操作'] not in action_mappings:
                LOGGER.warning("unsupported action: %s", row['操作'])
                continue

            order_time = datetime.strptime(f'{row["成交日期"]} {row["成交时间"]}', '%Y%m%d %H:%M:%S')
            action = action_mappings[row['操作']]
            code, name = row['证券代码'], row['证券名称']
            count, price = float(row['成交数量']), float(row['成交均价'])
            money = float(row['发生金额'].lstrip('-'))
            fee = float(row["手续费"]) + float(row["印花税"])
            if action.startswith('transfer') or action == 'reinvest':
                code, name, count, price = 'CASH', '现金', money, 1.0

            results.append([
                '平安证券', '平安证券', order_time, code, name,
                action, count, price, money, fee
            ])

    results.sort(key=itemgetter(2, 3, 5))
    with open(outfile, 'w') as fout:
        for row in results:
            print(
                f'{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}\t{row[4]}\t{row[5]}\t'
                f'{row[6]:.4f}\t{row[7]:.4f}\t{row[8]:.4f}\t{row[9]:.4f}',
                file=fout
            )


@main.command("parse-huabao")
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile", required=True)
def parse_huabao(infile, outfile):
    """解析华宝证券的交易记录"""
    ignore_actions = set(['中签通知', '配号'])
    action_mappings = {
        '买入': 'buy',
        '卖出': 'sell',
        '中签扣款': 'buy',
    }
    data = []
    stagging_data = []
    with open(infile) as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            if row['委托类别'] in ignore_actions:
                continue

            if row['委托类别'] not in action_mappings:
                # 将打新股/打新债的扣款、托管相关的交易记录另外记录待之后处理
                if row['委托类别'] in ('托管转入', '托管转出'):
                    stagging_data.append(row)
                    continue
                else:
                    LOGGER.warning("unsupported action: %s", row)

                continue

            order_time = datetime.strptime(f'{row["成交日期"]} {row["成交时间"]}', '%Y%m%d %H:%M:%S')
            action = action_mappings[row['委托类别']]
            money, fee = float(row['发生金额']), float(row['佣金']) + float(row['印花税'])
            if action == 'buy':
                money += fee
            elif action == 'sell':
                money -= fee

            # 有些品种用「手」作为单位，将其转换为「股」
            count, price = float(row['成交数量']), float(row['成交价格'])
            if abs(money / (float(count) * float(price)) - 10) < 0.5:
                count = float(count) * 10

            data.append((
                '华宝证券', '华宝证券', order_time, row['证券代码'], row['证券名称'],
                action, count, price, money, fee
            ))

    name2codes = defaultdict(dict)
    for row in stagging_data:
        if not row['证券名称'].strip():
            continue
        if row['委托类别'] == '托管转出' and row['成交编号'] == '清理过期数据':
            name2codes[row['证券名称']]['origin'] = row['证券代码']
        elif row['委托类别'] == '托管转入':
            name2codes[row['证券名称']]['new'] = row['证券代码']

    code_mappings = {}
    for codes in name2codes.values():
        code_mappings[codes['origin']] = codes['new']

    print(code_mappings)
    data.sort(key=itemgetter(2, 3, 5))
    with open(outfile, 'w') as fout:
        for row in data:
            row = list(row)
            if row[5] == 'buy' and row[3] in code_mappings:
                LOGGER.info("convert code from `%s` to `%s`", row[3], code_mappings[row[3]])
                row[3] = code_mappings[row[3]]

            print(
                f'{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}\t{row[4]}\t{row[5]}\t'
                f'{row[6]:.4f}\t{row[7]:.4f}\t{row[8]:.4f}\t{row[9]:.4f}',
                file=fout
            )


@main.command("create-db")
def create_db():
    """创建资产相关的数据库"""
    DATABASE.connect()
    DATABASE.create_tables([
        Deal,
        Fund,
        FundHistory,
        FundBonusHistory,
    ])
    DATABASE.close()


@main.command("update-fund")
@click.option("-c", "--code", required=True)
def update_fund(code):
    """增加或更新基金数据"""
    api = EastMoneyFundExporter()
    fund_data = api.get_fund_data(code)
    if fund_data is None:
        return

    fund = Fund.get_or_none(Fund.code == code)
    if not fund:
        fund = Fund.create(
            code=code,
            name=fund_data['fS_name'],
            min_purchace=float(fund_data['fund_minsg'] or 0)
        )

    if not fund_data.get('Data_netWorthTrend') or \
       not fund_data.get('Data_ACWorthTrend'):
        LOGGER.warning("nav or auc info is missing")
        return

    history, bonus_history = defaultdict(dict), []
    for nav in fund_data['Data_netWorthTrend']:
        date = str(datetime.fromtimestamp(nav['x'] / 1000).date())
        history[date]['nav'] = nav['y']
        if nav.get('unitMoney'):
            bonus_text = nav['unitMoney']
            action, value = 'unknown', None
            if bonus_text.startswith('分红'):
                action = 'bonus'
                value = float(re.findall(r'派现金(\d\.\d+)元', bonus_text)[0])
            elif bonus_text.startswith('拆分'):
                action = 'spin_off'
                value = float(re.findall(r'折算(\d\.\d+)份', bonus_text)[0])
            else:
                LOGGER.wanring("unknown bonus text: %s", bonus_text)

            if action != 'unknown':
                bonus_history.append((date, action, value))

    for auv in fund_data['Data_ACWorthTrend']:
        date = str(datetime.fromtimestamp(auv[0] / 1000).date())
        history[date]['auv'] = auv[1]

    cnt = 0
    for date, info in history.items():
        if 'nav' not in info or 'auv' not in info:
            LOGGER.warning("invalid history data: %s(%s)", info, date)
            continue

        date_value = datetime.strptime(date, '%Y-%m-%d').date()
        _, created = FundHistory.get_or_create(
            date=date_value,
            nav=info['nav'],
            auv=info['auv'],
            fund=fund
        )
        if created:
            cnt += 1

    LOGGER.info("%s: add %d nav records", code, cnt)

    cnt = 0
    for date, action, value in bonus_history:
        date_value = datetime.strptime(date, '%Y-%m-%d').date()
        _, created = FundBonusHistory.get_or_create(
            date=date_value,
            action=action,
            value=value,
            fund=fund
        )
        if created:
            cnt += 1

    LOGGER.info("%s: add %d bonus records", code, cnt)


@main.command()
@click.option("-i", "--infile", required=True)
def import_deals(infile):
    """从文件中批量导入交易"""
    with open(infile) as fin:
        reader = csv.reader(fin, delimiter='\t')
        cnt, total = 0, 0
        for row in reader:
            _, created = Deal.get_or_create(
                account=row[0],
                sub_account=row[1],
                time=datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S'),
                code=row[3],
                name=row[4],
                type=row[5],
                amount=row[6],
                price=row[7],
                money=row[8],
                fee=row[9]
            )
            total += 1
            if created:
                cnt += 1

        if cnt != total:
            LOGGER.warning("%d records are already in database", total - cnt)

        LOGGER.info("created %d records in database", cnt)


@main.command()
def validate_deals():
    """检查交易记录是否有缺失（如分红/拆分）或错误"""
    deals = defaultdict(list)
    for record in Deal.select().order_by(Deal.time):
        deals[record.code].append(record)

    for code, records in deals.items():
        fund = Fund.get_or_none(code=code)
        if not fund:
            continue

        bonus_history = list(
            fund.bonus_history.where(
                FundBonusHistory.date >= records[0].time.date()
            )
        )
        if not bonus_history:
            continue

        for bonus_record in bonus_history:
            matched = False
            for deal in records:
                if deal.time.date() == bonus_record.date:
                    matched = True
                    break

            if not matched:
                LOGGER.warning(
                    "bonus is missing in deals - fund: %s(%s), "
                    "date: %s, action: %s, value: %s",
                    fund.name, fund.code, bonus_record.date,
                    bonus_record.action, bonus_record.value
                )


@main.command("list-assets")
@click.option("--account")
@click.option("--sub-account")
def list_assets(account, sub_account):
    """列出当前持有的资产"""
    assets, code2name = defaultdict(float), {}

    search = Deal.select()
    if account:
        search = search.where(Deal.account == account)
    if sub_account:
        search = search.where(Deal.sub_account == sub_account)

    total_transfer_in = 0
    for item in search.order_by(Deal.time):
        if item.code not in code2name:
            code2name[item.code] = item.name

        if item.code not in assets:
            assets[item.code] = 0

        if item.type in ('buy', 'reinvest', 'transfer_in'):
            assets[item.code] += item.amount
            if item.type == 'buy':
                assets['CASH'] -= item.money
            if item.type == 'transfer_in':
                total_transfer_in += item.amount
        elif item.type in ('sell', 'transfer_out'):
            assets[item.code] -= item.amount
            if item.type == 'sell':
                assets['CASH'] += item.money
            if item.type == 'transfer_out':
                total_transfer_in -= item.amount
        elif item.type in ('bonus', 'fix_cash'):
            assets['CASH'] += item.amount
        elif item.type == 'spin_off':
            assets[item.code] = item.amount

    data = [
        (code, code2name[code] if code != 'CASH' else '现金', f'{amount:.4f}')
        for code, amount in sorted(assets.items(), key=itemgetter(1), reverse=True)
        if abs(amount) > 0.00001
    ]
    print('总投入:', total_transfer_in)
    print(
        tabulate(data,
                 headers=['code', 'name', 'amount'],
                 showindex='always',
                 stralign='center',
                 tablefmt='orgtbl')
    )


if __name__ == '__main__':
    main()
