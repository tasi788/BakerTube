from yt_dlp import YoutubeDL
import requests
from yaml import safe_load
import sys
import os
import logging
import coloredlogs
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)
coloredlogs.install(logger=logger)

if not os.path.exists('config.yml'):
    logger.fatal('找不到 config.yml')
    sys.exit(1)

raw_config = safe_load(open('config.yml', 'r').read())


class Config:
    class _Bot:
        token: str = raw_config['bot']['token']
        channel: str = raw_config['bot']['channel']

    bot: _Bot = _Bot

    class _Notion:
        token: str = raw_config['notion']['token']
        database: str = raw_config['notion']['database']
        version: str = raw_config['notion']['version']

    notion: _Notion = _Notion


@dataclass
class NotionData:
    title: str = field(repr=True)
    url: str = field(repr=True)


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
        lists = NotionList()
        for x in r_.json()['results']:
            lists.lists.append(NotionData(
                title=x['properties']['Name']['title'][-1]['plain_text'],
                url=x['properties']['URL']['url']))
        return lists


if __name__ == '__main__':
    notionlist = Notion()
    listing = notionlist.fetch()

    for video in listing.lists:
        if not os.path.exists(video.title):
            os.mkdir(video.title)

        ydl_opts = {
            'format': 'bestaudio+bestvideo',
            'cookiefile': './cookies.txt',
            'outtmpl': f'/plexdrive/[YouTube]/{video.title}/%(title)s.%(ext)s',
            'ratelimit': 1024 * 1024 * 10,
            'merge_output_format': 'mp4'
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video.url])
