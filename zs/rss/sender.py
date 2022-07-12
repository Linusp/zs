import re
from abc import ABC, abstractmethod

import requests
from lxml import html

SENDERS = {}


def register_sender(name):
    def wrap(cls):
        global SENDERS
        if name not in SENDERS:
            SENDERS[name] = cls

        return cls

    return wrap


def get_sender_cls(name):
    return SENDERS.get(name)


class Sender(ABC):
    def __init__(self, dest_url, content=None, **kwargs):
        self.dest_url = dest_url
        self.content = content or ["title", "images"]

    @abstractmethod
    def prepare_data(self, article):
        ...

    def send(self, article):
        data = self.prepare_data(article)
        if data:
            response = requests.post(
                self.dest_url, json=data, headers={"Content-Type": "application/json"}
            )
            return response


@register_sender("slack_incoming")
class SlackIncomingSender(Sender):

    IMG_PATTERN = re.compile(r"<img.*?src=\"(.*?)\"(?: ?/)?>")

    def __init__(self, dest_url, **kwargs):
        super().__init__(dest_url, **kwargs)
        self.channel = kwargs.get("channel", "general")
        self.filters = kwargs.get("filters", [])

    @staticmethod
    def extract_links(html_content):
        content = html.fromstring(html_content)
        links = []
        for link in content.iter("a"):
            url = link.get("href")
            text = link.text or ""
            if not url:
                continue

            if url.startswith("https://t.me"):
                continue

            links.append((text, url))

        return links

    @staticmethod
    def convert_html(html_content):
        content = html.fromstring(html_content)
        for bold_item in content.iter("b"):
            bold_text = bold_item.text or ""
            if bold_text:
                bold_item.text = f" *{bold_text}* "

        for ul_item in content.iter("ul"):
            for li_item in ul_item.iter("li"):
                li_text = li_item.text or ""
                if li_text:
                    li_item.text = f"- {li_text}"

        for ol_item in content.iter("ol"):
            for idx, li_item in enumerate(ol_item.iter("li")):
                li_text = li_item.text or ""
                if li_text:
                    li_item.text = f"{idx}. {li_text}"

        text = content.text_content().replace("\xa0", "").strip()
        text = re.sub(r"^#\S+(?: #\S+)*", "", text)
        return text

    def prepare_data(self, article):
        if self.filters and not any(article.summary.find(word) >= 0 for word in self.filters):
            return None

        blocks, links = [], []
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": f"from: *{article.feed.name}*"}}
        )
        if "title" in self.content:
            links.extend(self.extract_links(article.title))
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": self.convert_html(article.title)},
                }
            )

        if "summary" in self.content:
            links.extend(self.extract_links(article.summary))
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": self.convert_html(article.summary)},
                }
            )

        if links:
            link_text = "*相关链接*:\n"
            for text, link in links:
                if text:
                    link_text += f"- {text}: {link}\n"
                else:
                    link_text += f"- {link}\n"

            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": link_text}})

        imgs = [img.strip('"') for img in self.IMG_PATTERN.findall(article.summary)]
        if imgs and "images" in self.content:
            blocks += [{"type": "image", "image_url": img, "alt_text": "image"} for img in imgs]

        return {"channel": self.channel, "blocks": blocks}
