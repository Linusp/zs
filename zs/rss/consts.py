import os
import json


WORK_DIR = os.path.abspath(os.path.dirname(__file__))

KZ_SCENARIO_TEMPLATE = json.load(
    open(os.path.join(WORK_DIR, 'kz_scenario_template.json'))
)
EFB_SCENARIO_TEMPLATE = json.load(
    open(os.path.join(WORK_DIR, 'efb_scenario_template.json'))
)
