import re
import logging
from typing import NamedTuple

from requests import Session
import execjs


LOGGER = logging.getLogger(__name__)


class QiemanExporter:

    # source: https://gist.github.com/iwinux/30012ba5e21fba4580b2d2b74b934493
    BASE_URL = 'https://qieman.com/pmdj/v2'

    def __init__(self, aid, request_id, sign, token):
        self.headers = {
            'Authorization': f'Bearer {token}',
            'x-aid': aid,
            'x-request-id': request_id,
            'x-sign': sign,
        }
        self.http = Session()

    def list_orders(self, asset_id):
        for order in self._list_orders(asset_id):
            if order.get('hasDetail'):
                order = self._http_get(f'/orders/{order["orderId"]}')
                yield order
            else:
                yield order

    def _list_orders(self, asset_id):
        params = {'capitalAccountId': asset_id, 'size': 100, 'page': 0}

        while True:
            resp = self._http_get('/orders', params)
            yield from resp['content']

            if resp['last']:
                break

            params['page'] += 1

    def _http_get(self, path, params=None):
        url = f'{self.BASE_URL}{path}'
        resp = self.http.get(url, params=params, headers=self.headers)
        resp.raise_for_status()
        return resp.json()


class FundBasis(NamedTuple):

    code: str
    name: str
    category: str


class EastMoneyFundExporter:

    FUND_LIST_URL = 'http://fund.eastmoney.com/js/fundcode_search.js'
    JS_VAR_PATTERN = re.compile(r'var ([a-zA-Z_][a-zA-Z_\d]*) ?=')
    FUND_DATA_URL_TMP = 'http://fund.eastmoney.com/pingzhongdata/{code}.js'

    def __init__(self):
        self.http = Session()

    def list_funds(self):
        resp = self.http.get(self.FUND_LIST_URL)
        if resp.status_code != 200:
            LOGGER.warning(
                "failed to fetch fund list(%d: %s)",
                resp.status_code, resp.reason
            )
            return []

        js_data = execjs.compile(resp.text)
        funds = []
        for code, _, name, category, _ in js_data.eval('r'):
            funds.append(FundBasis(code=code, name=name, category=category))

        return funds

    def get_fund_data(self, fund_code):
        url = self.FUND_DATA_URL_TMP.format(code=fund_code)
        resp = self.http.get(url)
        if resp.status_code != 200:
            LOGGER.warning(
                "failed to get data of fund: %s(%d: %s)",
                fund_code, resp.status_code, resp.reason
            )
            return None

        content = resp.text
        js_data = execjs.compile(content)
        var_names = self.JS_VAR_PATTERN.findall(content)
        data = {}
        for var in var_names:
            data[var] = js_data.eval(var)

        return data
