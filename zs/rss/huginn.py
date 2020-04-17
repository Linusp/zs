from uuid import uuid4
from copy import deepcopy

from .consts import KZ_SCENARIO_TEMPLATE, EFB_SCENARIO_TEMPLATE


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
        if agent['type'] == 'Agents::DataOutputAgent':
            agent['options']['secrets'] = [f'wx-{wxid}']
            agent['options']['template']['title'] = name
            agent['options']['template']['description'] = f'公众号“{name}”更新 - 使用 Huginn 制作'

    return result
