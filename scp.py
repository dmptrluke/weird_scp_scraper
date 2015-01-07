import re
import json
import asyncio

import requests
from bs4 import BeautifulSoup

from cloudbot import hook
from cloudbot.util import web, formatting

from collections import defaultdict


class SCPError(Exception):
    pass

SOURCE_LISTS = [("http://www.scp-wiki.net/joke-scps", "joke"), ("http://www.scp-wiki.net/archived-scps", "archived"),
                ("http://www.scp-wiki.net/decommissioned-scps", "decommissioned"), ("http://www.scp-wiki.net/scp-ex", "explained"),
                ("http://www.scp-wiki.net/scp-series", "series 1"), ("http://www.scp-wiki.net/scp-series-2", "series 2"),
                ("http://www.scp-wiki.net/scp-series-3", "series 3")]

scp_re = re.compile(r"(www.scp-wiki.net/scp-([a-zA-Z0-9-]+))")

scp_db = []


class SCP():
    """
    Represents a SCPwiki entry!
    """
    id_index = defaultdict(list)
    title_index = defaultdict(list)

    def __init__(self, scp_id, lore_id, scp_class, category, title, description, url):
        self.scp_id = scp_id
        self.lore_id = lore_id
        self.scp_class = scp_class
        self.category = category
        self.title = title
        self.description = description
        self.url = url
        SCP.id_index[self.scp_id.lower().strip()].append(self)
        SCP.title_index[self.title.lower().strip()].append(self)

    def __repr__(self):
        return "\x02Item Name:\x02 {}, \x02Item #:\x02 {}, \x02Class\x02: {}," \
               " \x02Description:\x02 {}".format(self.title, self.scp_id, self.scp_class, self.description)


    @classmethod
    def find_by_id(cls, scp_id):
        return SCP.id_index[scp_id.lower().strip()]

    @classmethod
    def find_by_title(cls, title):
        return SCP.title_index[title.lower().strip()]

@hook.command
def dump(reply):
    to_dump = []
    for scp in scp_db:
        to_dump.append(scp.__dict__)

    reply("Dumping {} entries to JSON".format(len(to_dump)))

    with open("lol.json", 'w') as o:
        json.dump(to_dump, o, indent=4)

    reply("Dumping Complete")


@hook.command
def load(reply):


    with open("lol.json", 'r') as o:
        data = json.load(o)

    reply("Loading {} entries from JSON".format(len(data)))

    for scp in data:
        scp = SCP(scp['scp_id'], scp['lore_id'], scp['scp_class'], scp['category'], scp['title'], scp['description'], scp['url'])
        scp_db.append(scp)

    reply("Loading Complete")



@asyncio.coroutine
@hook.command
def get_data(loop, reply):
    reply("Dumper activated, do not touch bot.")
    for url, category in SOURCE_LISTS:
        reply("Processing URL: " + url)
        request = yield from loop.run_in_executor(None, requests.get, url)
        soup = BeautifulSoup(request.text)


        page = soup.find('div', {'id': 'page-content'}).find('div', {'class': 'content-panel standalone series'})
        names = page.find_all("a", text=re.compile(r"SCP-"))
        for item in names:
            scp_id = item.text
            if SCP.find_by_id(scp_id):
                print("Skipping " + scp_id + ", already loaded")
                continue
            title = item.parent.contents[1][3:].strip()
            url = "http://www.scp-wiki.net" + item['href']
            try:
                lore_id, scp_class, description = yield from loop.run_in_executor(None, get_info, url)
            except SCPError:
                continue

            scp = SCP(scp_id, lore_id, scp_class, category, title, description, url)
            scp_db.append(scp)
            print(scp)

    reply("Dumping Completed")



def get_info(url):
    """ Takes a SCPWiki URL and returns a formatted string """
    try:
        request = requests.get(url)
        request.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
        raise SCPError("Error: Unable to fetch URL. ({})".format(e))
    html = request.text
    contents = formatting.strip_html(html)

    try:
        scp_id = re.findall("Item #: (.+?)\n", contents, re.S)[0]
        scp_class = re.findall("Object Class: (.+?)\n", contents, re.S)[0]
        description = re.findall("Description: (.+?)\n", contents, re.S)[0]
    except IndexError:
        raise SCPError("Error: Invalid or unreadable SCP. Does this SCP exist?")

    description = formatting.truncate_str(description, 250)
    return scp_id, scp_class, description


@hook.command
def scpdb(text):
    """scp <query>/<item id> -- Returns SCP Foundation wiki search result for <query>/<item id>."""
    if not text.isdigit():
        term = text
    else:
        if len(text) == 4:
            term = "SCP-" + text
        elif len(text) == 3:
            term = "SCP-" + text
        elif len(text) == 2:
            term = "SCP-0" + text
        elif len(text) == 1:
            term = "SCP-00" + text
        else:
            term = text

    # search for the SCP
    return SCP.find_by_id(term)
