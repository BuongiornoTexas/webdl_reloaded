#!/usr/bin/env python3

import requests_cache
from common import grab_html, grab_json, grab_xml, download_hls, Node, append_to_qs

import json
import logging
import os
import sys

BASE = "https://www.sbs.com.au"
FULL_VIDEO_LIST = BASE + "/api/video_feed/f/Bgtm9B/sbs-section-programs/"
VIDEO_SMIL_URL = BASE + "/api/v3/video_smil?id="

NS = {
    "smil": "http://www.w3.org/2005/SMIL21/Language",
}


class SbsVideoNode(Node):
    def __init__(self, title, parent, url):
        Node.__init__(self, title, parent)
        self.video_id = url.split("/")[-1]
        self.can_download = True

    def download(self):
        filename = self.title + ".ts"

        with requests_cache.disabled():
            doc = grab_xml(VIDEO_SMIL_URL + self.video_id)
            video_el = doc.xpath("//smil:video", namespaces=NS)
            if not video_el:
                print("Cannot find video:", error)
                return False
            video_url = video_el[0].attrib["src"]

        return download_hls(filename, video_url)

class SbsNavNode(Node):
    def create_video_node(self, entry_data):
        SbsVideoNode(entry_data["title"], self, entry_data["id"])

    def find_existing_child(self, path):
        for child in self.children:
            if child.title == path:
                return child

class SbsRootNode(SbsNavNode):
    def __init__(self, parent: Node):
        """Initialise SBS root."""
        super().__init__("SBS", parent)

    def _fill_children(self):
        all_video_entries = self.load_all_video_entries()
        category_and_entry_data = self.explode_videos_to_unique_categories(all_video_entries)
        for category_path, entry_data in category_and_entry_data:
            nav_node = self.create_nav_node(self, category_path)
            nav_node.create_video_node(entry_data)

    def load_all_video_entries(self):
        channels = [
            "Channel/NITV",
            "Channel/SBS1",
            "Channel/SBS Food",
            "Channel/SBS VICELAND",
            "Channel/SBS World Movies",
            "Channel/Web Exclusive",
        ]

        all_entries = {}
        for channel in channels:
            self.load_all_video_entries_for_channel(all_entries, channel)

        all_entries = list(all_entries.values())
        print(" SBS fetched", len(all_entries))
        return all_entries

    def load_all_video_entries_for_channel(self, all_entries, channel):
        offset = 1
        page_size = 500
        duplicate_warning = False

        while True:
            entries = self.fetch_entries_page(channel, offset, page_size)
            if len(entries) == 0:
                break

            for entry in entries:
                guid = entry["guid"]
                if guid in entries and not duplicate_warning:
                    # https://bitbucket.org/delx/webdl/issues/102/recent-sbs-series-missing
                    logging.warn("SBS returned a duplicate response, data is probably missing. Try decreasing page_size.")
                    duplicate_warning = True

                all_entries[guid] = entry

            offset += page_size
            if os.isatty(sys.stdout.fileno()):
                sys.stdout.write(".")
                sys.stdout.flush()

    def fetch_entries_page(self, channel, offset, page_size):
        url = append_to_qs(FULL_VIDEO_LIST, {
            "range": "%s-%s" % (offset, offset+page_size-1),
            "byCategories": channel,
        })
        data = grab_json(url)
        if "entries" not in data:
            raise Exception("Missing data in SBS response", data)
        return data["entries"]

    def explode_videos_to_unique_categories(self, all_video_entries):
        for entry_data in all_video_entries:
            for category_data in entry_data["media$categories"]:
                category_path = self.calculate_category_path(
                    category_data["media$scheme"],
                    category_data["media$name"],
                )
                if category_path:
                    yield category_path, entry_data

    def calculate_category_path(self, scheme, name):
        if not scheme:
            return
        if scheme == name:
            return
        name = name.split("/")
        if name[0] != scheme:
            name.insert(0, scheme)
        return name

    def create_nav_node(self, parent, category_path):
        if not category_path:
            return parent

        current_path = category_path[0]
        current_node = parent.find_existing_child(current_path)
        if not current_node:
            current_node = SbsNavNode(current_path, parent)
        return self.create_nav_node(current_node, category_path[1:])
