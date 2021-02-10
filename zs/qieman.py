# source: https://gist.github.com/iwinux/30012ba5e21fba4580b2d2b74b934493
from requests import Session


class QiemanExporter:

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
