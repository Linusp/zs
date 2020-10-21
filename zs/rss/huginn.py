from uuid import uuid4
from copy import deepcopy

import feedparser

from .consts import KZ_SCENARIO_TEMPLATE, EFB_SCENARIO_TEMPLATE, DAILY_DIGEST_SCENARIO_TEMPLATE


def generate_kz_scenario(name, wxid, topic_id, rsshub_base_url='https://rsshub.app'):
    result = deepcopy(KZ_SCENARIO_TEMPLATE)
    result['name'] = "微信公众号 - {}".format(name)
    result['description'] = '微信公众号“{}” RSS 输出'.format(name)
    result['guid'] = str(uuid4()).replace('-', '')
    for agent in result['agents']:
        agent['guid'] = str(uuid4()).replace('-', '')
        if agent['type'] == 'Agents::DataOutputAgent':
            agent['options']['secrets'] = [f'wx-{wxid}']
            agent['options']['template']['title'] = name
            agent['options']['template']['description'] = f'公众号“{name}”更新 - 使用 Huginn 制作'
        if agent['type'] == 'Agents::RssAgent':
            agent['options']['url'] = [
                f'{rsshub_base_url}/kzfeed/topic/{topic_id}'
            ]

    return result


def generate_efb_scenario(name, wxid):
    result = deepcopy(EFB_SCENARIO_TEMPLATE)
    result['name'] = "微信公众号 - {}".format(name)
    result['description'] = '微信公众号“{}” RSS 输出'.format(name)
    result['guid'] = str(uuid4()).replace('-', '')
    for agent in result['agents']:
        agent['guid'] = str(uuid4()).replace('-', '')
        agent['name'] = agent['name'].format(name)
        if agent['type'] == 'Agents::DataOutputAgent':
            agent['options']['secrets'] = [f'wx-{wxid}']
            agent['options']['template']['title'] = name
            agent['options']['template']['description'] = f'公众号“{name}”更新 - 使用 Huginn 制作'

    return result


def generate_daily_digest_scenario(feed_url, name=None, description=None):
    result = deepcopy(DAILY_DIGEST_SCENARIO_TEMPLATE)

    feed_info = feedparser.parse(feed_url)['feed']

    result['name'] = name or f'{feed_info["title"]} · 每日摘要'
    result['guid'] = str(uuid4()).replace('-', '')

    for agent in result['agents']:
        if agent['type'] == 'Agents::RssAgent':
            agent['options']['url'] = feed_url
        elif agent['type'] == 'Agents::EventFormattingAgent':
            if name:
                agent['options']['instructions']['title'] = name + \
                    agent['options']['instructions']['title']
        elif agent['type'] == 'Agents::DataOutputAgent':
            agent['options']['secrets'] = [str(uuid4())]
            agent['options']['template']['title'] = f'{name or feed_info["title"]}-每日摘要'
            agent['options']['template']['description'] = description or f'{feed_info["subtitle"]}'
            agent['options']['template']['item']['link'] = feed_info.get('link') or ''

    return result
