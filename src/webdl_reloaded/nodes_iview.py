#!/usr/bin/env python3
# cspell:ignore iview webdl
"""Provides media nodes for ABC iView."""

import string
import time
import hashlib
import hmac

# TODO eliminate if possible.
from typing import Any
import requests_cache

from node import AbstractNode
from common import append_to_qs, grab_json, grab_text, download_hls

BASE_URL = "https://iview.abc.net.au"
API_URL = "https://iview.abc.net.au/api"


class IViewMediaNode(AbstractNode):
    """Downloadable iView media Node."""

    # In future, provide these by pydantic BaseModel.
    video_key: str

    # TODO Eliminate __init__ when converting to pydantic.
    def __init__(self, title: str, video_key: str) -> None:
        """Initialise iView media node."""
        super().__init__(title)
        self.video_key = video_key

        # TODO These two need to be done in the pydantic post_init.
        self.filename = title + ".ts"
        self.can_download = True

    def _fill_children(self) -> None:
        """Load child nodes."""
        # Downloadable leaf. No children.
        self._children = []

    # TODO fix JSON annotation if we need to keep playlist info.
    def find_hls_url(self, playlist: Any) -> str:
        """Find hls."""
        # TODO Replace with yt-dlp external call.
        for video in playlist:
            if video["type"] in ["program", "livestream"]:
                streams = video["streams"]["hls"]
                for quality in ["720", "sd", "sd-low"]:
                    if quality in streams:
                        return streams[quality]
        raise RuntimeError(
            "Missing program stream for " + self.video_key + " -- " + self.title
        )

    def get_auth_token(self) -> str:
        """Get auth token."""
        # TODO Replace with yt-dlp external call? May still be needed.
        path = "/auth/hls/sign?ts=%s&hn=%s&d=android-tablet" % (
            int(time.time()),
            self.video_key,
        )
        sig = hmac.new(
            b"android.content.res.Resources", path.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        auth_url = BASE_URL + path + "&sig=" + sig
        with requests_cache.disabled():
            auth_token = grab_text(auth_url)
        return auth_token

    def download(self) -> bool:
        """Download media file (returns True on success)."""
        # TODO Replace/update with yt-dlp call.
        info = grab_json(API_URL + "/programs/" + self.video_key)
        if "playlist" not in info:
            return False
        video_url = self.find_hls_url(info["playlist"])
        auth_token = self.get_auth_token()
        video_url = append_to_qs(
            video_url, {"hdnea": auth_token}  # cspell:disable-line
        )
        return download_hls(self.filename, video_url)


class IviewIndexNode(AbstractNode):
    """General iView navigation node."""

    url: str
    # TODO Check unique series initialisation when converting to pydantic.
    # TODO Clean up implementation of unique_series?
    unique_series: set[str] = set()

    # TODO Eliminate __init__ when converting to pydantic.
    def __init__(self, title: str, url: str) -> None:
        """Initialise iView index node."""
        super().__init__(title)
        self.url = url

    def _fill_children(self) -> None:
        """Create list of children."""
        self._children = []
        info = grab_json(self.url)
        for key in ["carousels", "collections", "index"]:
            for collection_list in info.get(key, None):
                if isinstance(collection_list, dict):
                    for ep_info in collection_list.get("episodes", []):
                        title = ep_info["seriesTitle"]
                        if title in self.unique_series:
                            # Already added.
                            continue
                        self.unique_series.add(title)
                        url = API_URL + "/" + ep_info["href"]
                        self._children.append(
                            IViewMediaContainerNode(title, url, series_container=True)
                        )


class IViewMediaContainerNode(AbstractNode):
    """Container Node for series and "flat" collections like "Featured"."""

    # In future, provide these by pydantic BaseModel.
    url: str
    # If have more than one type, make this an enum.
    # for iView, we have series and thing things like the featured page.
    series_container: bool

    # TODO Eliminate __init__ when converting to pydantic.
    def __init__(self, title: str, url: str, series_container: bool) -> None:
        """Initialise iView container node."""
        super().__init__(title)
        self.url = url
        self.series_container = series_container

    def _fill_children(self) -> None:
        """Create container node children."""
        if self.series_container:
            # Most typical container for iView media Nodes.
            series_info = grab_json(self.url)
            series_slug = series_info["href"].split("/")[1]
            series_url = (
                API_URL
                + "/series/"
                + series_slug
                + "/"
                + series_info["seriesHouseNumber"]
            )
            episodes_list = grab_json(series_url).get("episodes", [])
        else:
            # Dealing with something like the features page.
            # Previously an IViewFlatNode in OG webdl.
            # Which turns out to be much simpler
            episodes_list = grab_json(self.url)

        self._children = []
        for episode in episodes_list:
            video_key = episode["episodeHouseNumber"]
            series_title = episode["seriesTitle"]
            episode_title = episode.get("title", None)

            if episode_title:
                episode_title = series_title + " " + episode_title
            else:
                # How it's done on the Featured page.
                episode_title = series_title

            self._children.append(IViewMediaNode(episode_title, video_key))


class IViewCategoryContainerNode(AbstractNode):
    """iView category container class."""

    def _fill_children(self) -> None:
        """Fill iView category nodes."""
        data = grab_json(API_URL + "/categories")
        categories = data["categories"]

        self._children = []
        for category_data in categories:
            category_title = category_data["title"]
            category_title = string.capwords(category_title)

            category_href = category_data["href"]

            self._children.append(
                IviewIndexNode(category_title, API_URL + "/" + category_href)
            )


class IViewChannelContainerNode(AbstractNode):
    """Container node for channels."""

    def _fill_children(self) -> None:
        """Create channel children nodes."""
        data = grab_json(API_URL + "/channel")
        channels = data["channels"]

        self._children = []
        for channel_data in channels:
            channel_id = channel_data["categoryID"]
            channel_title = {
                "abc1": "ABC1",
                "abc2": "ABC2",
                "abc3": "ABC3",
                "abc4kids": "ABC4Kids",
                "news": "News",
                "abcarts": "ABC Arts",
            }.get(channel_id, channel_data["title"])

            channel_href = channel_data["href"]

            self._children.append(
                IviewIndexNode(channel_title, API_URL + "/" + channel_href)
            )


class IViewRootNode(AbstractNode):
    """Root node for iView tree."""

    # __init__ from super class. Handle in pydantic in future.

    def _fill_children(self) -> None:
        self._children = [
            IViewCategoryContainerNode("By Category"),
            IViewChannelContainerNode("By Channel"),
            IViewMediaContainerNode(
                "Featured", API_URL + "/featured", series_container=False
            ),
        ]
