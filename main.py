import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from time import sleep
from typing import List

import coloredlogs
import requests
from yaml import safe_load
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)
coloredlogs.install(logger=logger)

if not os.path.exists('config.yml'):
    logger.fatal('找不到 config.yml')
    sys.exit(1)

raw_config = safe_load(open('config.yml', 'r').read())


class Config:
    class _Bot:
        url: str = raw_config['bot']['url']

    bot: _Bot = _Bot

    class _Notion:
        token: str = raw_config['notion']['token']
        database: str = raw_config['notion']['database']
        version: str = raw_config['notion']['version']

    notion: _Notion = _Notion

    class BackupPath:
        path: str = raw_config['backuppath']

    backuppath: BackupPath = field(repr=True, default='')


@dataclass
class NotionData:
    title: str = field(repr=True)
    url: str = field(repr=True)
    membership: bool = field(repr=True, default=False)


@dataclass
class NotionList:
    lists: List[NotionData] = field(repr=True, default_factory=list)


class Notion:
    def __init__(self):
        self.base_url = 'https://api.notion.com/v1/'
        self.headers = {'Authorization': f'Bearer {Config.notion.token}',
                        'Notion-Version': Config.notion.version}
        self.session = requests.session()
        self.session.headers.update(self.headers)
        self._self_check()

    def _self_check(self):
        r = self.session.get(self.base_url + 'users')
        if r.status_code != 200:
            logger.fatal('Notion 驗證錯誤')
            sys.exit(1)

    def query(self):
        data = {
            'filter': {
                'property': 'Name',
                'rich_text': {
                    'is_not_empty': True}}}
        r = self.session.post(self.base_url + f'databases/{Config.notion.database}/query', json=data)
        return r

    def fetch(self):
        r_ = self.query()
        if r_.status_code != 200:
            logger.info(f'[{r_.status_code}] - 讀取 notion 清單錯誤')
            sys.exit(1)
        lists = NotionList()
        for x in r_.json()['results']:
            lists.lists.append(NotionData(
                title=x['properties']['Name']['title'][-1]['plain_text'],
                url=x['properties']['URL']['url'],
                membership=x['properties']['Membership']['checkbox']))
        return lists


def notify(d: dict):
    if d['status'] == 'finished':
        data = {
            "content": "✨ 已備份",
            "embeds": [{
                "title": d['info_dict']['fulltitle'],
                "url": d['info_dict']['webpage_url'],
                "type": "rich",
                "description": f"📂 [YouTube] - {d['info_dict']['channel']}",
                "image": {"url": d['info_dict']['thumbnail']}
            }]
        }
        requests.post(Config.bot.url, json=data)
        filepath = d['info_dict']['filepath']
        channel_safe = filepath.split('/')[2]
        moveto = f'{Config.BackupPath.path}/{channel_safe}'
        if not os.path.exists(moveto):
            try:
                os.mkdir(moveto)
            except Exception as e:
                logger.exception(e)
        try:
            shutil.move(filepath, moveto)
        except shutil.SameFileError:
            pass
        except shutil.Error as e:
            logger.error(f'移動 {moveto} 時發生錯誤')
            logger.error(e.__str__)


if __name__ == '__main__':
    while True:
        notionlist = Notion()
        listing = notionlist.fetch()
        for video in listing.lists:
            ydl_opts = {
                'format': 'bestaudio+bestvideo',
                'cookiefile': './cookies.txt',
                'outtmpl': f'./download/%(channel)s/%(title)s.%(ext)s',
                'ratelimit': 1024 * 1024 * 10,
                'merge_output_format': 'mp4',
                'postprocessor_hooks': [notify],
                'external_downloader': 'aria2c',
                'download_archive': './record.txt'
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video.url])

            if video.membership:
                ydl_opts.update({'outtmpl': f'{Config.BackupPath.path}membership/{video.title}/%(title)s.%(ext)s'})
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video.url + '/membership'])
        sleep(300)
