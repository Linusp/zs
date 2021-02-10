import os
import re
import json
from glob import glob
from logging.config import dictConfig

import click

from zs.consts import (
    README_TEMPLATE,
    SETUP_FILE_TEMPLATE,
    MAKEFILE_TEMPLATE,
    SETUP_CFG,
    IGNORE_FILE_TEMPLATE,
)
from zs.qieman import QiemanExporter


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


@main.command()
@click.option("-i", "--infile", required=True)
@click.option("-o", "--outfile")
def decode(infile, outfile):
    """对 json 文件进行格式化"""
    outfile = outfile or infile
    data = None
    with open(infile) as fin:
        data = json.load(fin)

    with open(outfile, 'w') as fout:
        json.dump(data, fout, ensure_ascii=False, indent=4, sort_keys=True)


@main.command("refine-img")
@click.option("-i", "--input-dir", required=True)
def refine_image_url(input_dir):
    """修正 HTML 中的 img 链接"""
    for html_file in glob(input_dir + '/*.html'):
        lines = []
        with open(html_file) as f:
            for line in f:
                lines.append(line.rstrip('\n'))

        with open(html_file, 'w') as f:
            for line in lines:
                line = re.sub(r'(?:\.\./){1,3}assets/img/', '/assets/img/', line)
                print(line, file=f)


@main.command("init-pyrepo")
@click.option("-n", "--repo-name", required=True)
@click.option("-p", "--python-version", default="3")
def init_pyrepo(repo_name, python_version):
    """使用模板创建 Python 新项目"""
    os.mkdir(repo_name)

    # create README
    fout = open(os.path.join(repo_name, 'README.md'), 'w')
    fout.write(README_TEMPLATE.format(name=repo_name, version=python_version))
    fout.close()

    # create setup.py
    fout = open(os.path.join(repo_name, 'setup.py'), 'w')
    fout.write(SETUP_FILE_TEMPLATE.format(name=repo_name))
    fout.close()

    # create requirements.txt
    fout = open(os.path.join(repo_name, 'requirements.in'), 'w')
    fout.close()
    fout = open(os.path.join(repo_name, 'requirements.txt'), 'w')
    fout.close()

    # create Makefile
    fout = open(os.path.join(repo_name, 'Makefile'), 'w')
    fout.write(MAKEFILE_TEMPLATE.format(name=repo_name, version=python_version))
    fout.close()

    # create project
    os.mkdir(os.path.join(repo_name, repo_name))
    os.mknod(os.path.join(repo_name, repo_name, '__init__.py'))
    os.mknod(os.path.join(repo_name, repo_name, 'consts.py'))
    os.mknod(os.path.join(repo_name, repo_name, 'utils.py'))

    # create tests
    os.mkdir(os.path.join(repo_name, 'tests'))
    fout = open(os.path.join(repo_name, 'setup.cfg'), 'w')
    fout.write(SETUP_CFG)
    fout.close()
    fout = open(os.path.join(repo_name, 'tests', '__init__.py'), 'w')
    fout.close()
    fout = open(os.path.join(repo_name, 'tests', 'conftest.py'), 'w')
    fout.close()

    # create gitignore
    fout = open(os.path.join(repo_name, '.gitignore'), 'w')
    fout.write(IGNORE_FILE_TEMPLATE)
    fout.close()


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
def parse_qieman_orders(infile, outfile):
    """解析且慢订单记录为 csv 格式"""
    import csv
    from datetime import datetime

    with open(infile) as fin, open(outfile, 'w') as fout:
        pattern = re.compile(r'再投资份额(\d+\.\d+)份')
        writer = csv.writer(fout, delimiter='\t', quoting=csv.QUOTE_ALL)
        writer.writerow([
            '账户', '名称', '代码', '类型', '时间', '价格',
            '份额', '金额', '手续费', '资金来源', '资金去向'
        ])
        account = None
        for line in fin:
            item = json.loads(line)
            if not account:
                account = item['umaName']

            if item['capitalAccountName'] == '货币三佳':
                if item['uiOrderCodeName'].find('盈米宝') < 0 or item['orderStatus'] != 'SUCCESS':
                    continue

                fund_code = item['po']['poCode']
                fund_name = item['po']['poName']
                action, buy_from, sell_to = 'unknown', '', ''
                if item['payStatus'] == '2':
                    action = 'buy'
                    buy_from = '盈米宝'
                elif item['payStatus'] == '0':
                    action = 'sell'
                    sell_to = '盈米宝'

                value = 1.0
                fee = item['totalFee']
                count = money = item['uiAmount']
                order_time = datetime.fromtimestamp(item['acceptTime'] / 1000)
                writer.writerow([
                    account, fund_name, fund_code, action, order_time,
                    f'{value:.4f}', f'{count:.4f}', f'{money:.4f}', f'{fee:.4f}',
                    buy_from, sell_to
                ])
            elif item['hasDetail']:
                if item['orderStatus'] != 'SUCCESS':
                    continue

                for order in item['compositionOrders']:
                    value = order['nav']
                    fee = order['fee']
                    order_time = datetime.fromtimestamp(order['acceptTime'] / 1000)
                    count = order['uiShare']
                    money = order['uiAmount']
                    action, buy_from, sell_to = 'unknown', '', ''
                    if order['payStatus'] == '2':
                        action = 'buy'
                        buy_from = '盈米宝'
                    elif order['payStatus'] == '0':
                        action = 'sell'
                        sell_to = '盈米宝'

                    fund_code = order['fund']['fundCode']
                    fund_name = order['fund']['fundName']
                    writer.writerow([
                        account, fund_name, fund_code, action, order_time,
                        f'{value:.4f}', f'{count:.4f}', f'{money:.4f}', f'{fee:.4f}',
                        buy_from, sell_to
                    ])
            elif item['uiOrderDesc'].find('再投资') >= 0:
                fee = 0
                order_time = datetime.fromtimestamp(item['acceptTime'] / 1000)
                count = float(pattern.findall(item['uiOrderDesc'])[0])
                money = item['uiAmount']
                value = float(money) / float(count)
                action = 'reinvest'
                fund_code = item['fund']['fundCode']
                fund_name = item['fund']['fundName']
                writer.writerow([
                    account, fund_name, fund_code, action, order_time,
                    f'{value:.4f}', f'{count:.4f}', f'{money:.4f}', f'{fee:.4f}', '', ''
                ])


if __name__ == '__main__':
    main()
