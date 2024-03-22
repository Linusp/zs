import json
import logging
import os
import re
import time
from glob import glob
from logging.config import dictConfig
from operator import itemgetter

import click
import requests

from zs.consts import (
    IGNORE_FILE_TEMPLATE,
    MAKEFILE_TEMPLATE,
    README_TEMPLATE,
    SETUP_CFG,
    SETUP_FILE_TEMPLATE,
)

dictConfig(
    {
        "version": 1,
        "formatters": {
            "simple": {
                "format": "%(asctime)s - %(filename)s:%(lineno)s: %(message)s",
            }
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "__main__": {"handlers": ["default"], "level": "DEBUG", "propagate": True},
            "zs": {"handlers": ["default"], "level": "DEBUG", "propagate": True},
        },
    }
)
LOGGER = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
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

    with open(outfile, "w") as fout:
        json.dump(data, fout, ensure_ascii=False, indent=4, sort_keys=True)


@main.command("refine-img")
@click.option("-i", "--input-dir", required=True)
def refine_image_url(input_dir):
    """修正 HTML 中的 img 链接"""
    for html_file in glob(input_dir + "/*.html"):
        lines = []
        with open(html_file) as f:
            for line in f:
                lines.append(line.rstrip("\n"))

        with open(html_file, "w") as f:
            for line in lines:
                line = re.sub(r"(?:\.\./){1,3}assets/img/", "/assets/img/", line)
                print(line, file=f)


@main.command("init-pyrepo")
@click.option("-n", "--repo-name", required=True)
@click.option("-p", "--python-version", default="3")
def init_pyrepo(repo_name, python_version):
    """使用模板创建 Python 新项目"""
    os.mkdir(repo_name)

    # create README
    fout = open(os.path.join(repo_name, "README.md"), "w")
    fout.write(README_TEMPLATE.format(name=repo_name, version=python_version))
    fout.close()

    # create setup.py
    fout = open(os.path.join(repo_name, "setup.py"), "w")
    fout.write(SETUP_FILE_TEMPLATE.format(name=repo_name))
    fout.close()

    # create requirements.txt
    fout = open(os.path.join(repo_name, "requirements.in"), "w")
    fout.close()
    fout = open(os.path.join(repo_name, "requirements.txt"), "w")
    fout.close()

    # create Makefile
    fout = open(os.path.join(repo_name, "Makefile"), "w")
    fout.write(MAKEFILE_TEMPLATE.format(name=repo_name, version=python_version))
    fout.close()

    # create project
    os.mkdir(os.path.join(repo_name, repo_name))
    os.mknod(os.path.join(repo_name, repo_name, "__init__.py"))
    os.mknod(os.path.join(repo_name, repo_name, "consts.py"))
    os.mknod(os.path.join(repo_name, repo_name, "utils.py"))

    # create tests
    os.mkdir(os.path.join(repo_name, "tests"))
    fout = open(os.path.join(repo_name, "setup.cfg"), "w")
    fout.write(SETUP_CFG)
    fout.close()
    fout = open(os.path.join(repo_name, "tests", "__init__.py"), "w")
    fout.close()
    fout = open(os.path.join(repo_name, "tests", "conftest.py"), "w")
    fout.close()

    # create gitignore
    fout = open(os.path.join(repo_name, ".gitignore"), "w")
    fout.write(IGNORE_FILE_TEMPLATE)
    fout.close()


def fetch_bili_history(cookies, page_num=10, page_size=100, delay=1.0):
    headers = {
        "Connection": "keep-alive",
        "Host": "api.bilibili.com",
        "Referer": "https://www.bilibili.com/account/history",
        "User-Agent": (
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) " "Gecko/20100101 Firefox/90.0"
        ),
    }
    session = requests.Session()
    url = "https://api.bilibili.com/x/v2/history"
    params = {"pn": 0, "ps": page_size, "jsonp": "jsonp"}
    history = []
    for page in range(page_num):
        params["pn"] = page
        resp = session.get(url, params=params, headers=headers, cookies=cookies)
        if resp.status_code != 200:
            LOGGER.error("bad response: %s(%s)", resp.reason, resp.status_code)
            break

        result = resp.json()
        if result.get("code") != 0 or not result.get("data"):
            LOGGER.error("bad response: %s", result)
            break

        history.extend(result["data"])
        if page < page_num - 1:
            LOGGER.info("fetched %d items", len(result["data"]))
            time.sleep(delay)

    return history


@main.command("get-bili-history")
@click.option("-c", "--cookie-file", required=True)
@click.option("-o", "--outfile", required=True)
@click.option("--page-size", type=int, default=100)
@click.option("--page-num", type=int, default=10)
@click.option("--delay", type=float, default=1.0)
def get_bili_history(cookie_file, outfile, page_size, page_num, delay):
    """下载B站观看历史数据"""
    cookies = json.load(open(cookie_file))
    history = fetch_bili_history(cookies, page_num=page_num, page_size=page_size, delay=delay)

    if os.path.exists(outfile):
        origin = []
        with open(outfile) as f:
            origin = json.load(f)

        id2item = {(item["kid"], item["view_at"]): item for item in origin}
        for item in history:
            if (item["kid"], item["view_at"]) in id2item:
                continue

            origin.append(item)

        origin.sort(key=itemgetter("view_at"))
        with open(outfile, "w") as fout:
            json.dump(origin, fout, ensure_ascii=False, indent=2)
    else:
        history.sort(key=itemgetter("view_at"))
        with open(outfile, "w") as fout:
            json.dump(history, fout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
