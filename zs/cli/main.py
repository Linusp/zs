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


if __name__ == '__main__':
    main()
