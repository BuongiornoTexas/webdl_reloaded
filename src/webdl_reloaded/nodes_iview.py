#!/usr/bin/env python3
# cspell:ignore iview webdl
"""Provides media nodes for ABC iView."""

import string

from webdl_reloaded.node import AbstractNode
from webdl_reloaded.common import grab_json

IVIEW_ID = "ABC iView"
BASE_URL = "https://iview.abc.net.au/"
VIDEO_URL = BASE_URL + "/video/"
API_URL = "https://iview.abc.net.au/api/"


class IViewMediaNode(AbstractNode):
    """Downloadable iView media Node."""

    # In future, provide these by pydantic BaseModel.
    _video_key: str

    def __init__(self, title: str, video_key: str) -> None:
        """Initialise iView media node."""
        super().__init__(title)

        self._video_key = video_key

        # See _load_media_url for lazy load implementation.
        # Downloadable node, so initialise _media_url with empty string.
        self._media_url = ""

    def _get_media_url(self) -> str:
        """Return media url. Lazy load if needed."""
        if self._media_url:
            # Loaded previously. Return value.
            return self._media_url

        # For ABC, it looks as yt-dlp can get everything it needs from
        # this url (subs, images, etc.), so not much of a lazy load.
        self._media_url = VIDEO_URL + self._video_key
        return self._media_url

        # This is the OG webdl version, which seems like overkill for yt-dlp.
        # Lazy load.
        # info = grab_json(API_URL + "programs/" + self._video_key)
        # if "href" not in info:
        #    return ""
        # return BASE_URL + info["href"]

    def _fill_children(self) -> None:
        """Load child nodes."""
        # Downloadable leaf. No children.
        self._children = []


class IviewIndexNode(AbstractNode):
    """General iView navigation node."""

    url: str
    # TODO Check and maybe clean up implementation of unique_series?
    unique_series: set[str]

    def __init__(self, title: str, url: str) -> None:
        """Initialise iView index node."""
        super().__init__(title)
        # TODO Maybe this can be converted to a class variable to minimise duplicate
        # nodes.
        self.unique_series = set()
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
                        url = API_URL + ep_info["href"]
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
                + "series/"
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
        data = grab_json(API_URL + "categories")
        categories = data["categories"]

        self._children = []
        for category_data in categories:
            category_title = category_data["title"]
            category_title = string.capwords(category_title)

            category_href = category_data["href"]

            self._children.append(
                IviewIndexNode(category_title, API_URL + category_href)
            )


class IViewChannelContainerNode(AbstractNode):
    """Container node for channels."""

    def _fill_children(self) -> None:
        """Create channel children nodes."""
        data = grab_json(API_URL + "channel")
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

            self._children.append(IviewIndexNode(channel_title, API_URL + channel_href))


class IViewRootNode(AbstractNode):
    """Root node for iView tree."""

    # __init__ from super class. Handle in pydantic in future.

    def _fill_children(self) -> None:
        self._children = [
            IViewCategoryContainerNode("By Category"),
            IViewChannelContainerNode("By Channel"),
            IViewMediaContainerNode(
                "Featured", API_URL + "featured", series_container=False
            ),
        ]
