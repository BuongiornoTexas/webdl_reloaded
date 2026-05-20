#!/usr/bin/env python3
# cspell:ignore webdl
"""Provides media nodes for 10Play."""

import logging
from typing import Any

from webdl_reloaded.common import append_to_query_string, grab_json
from webdl_reloaded.node import AbstractNode

TEN_ID = "Ten"
SERIES_LIST_URL = "https://vod.ten.com.au/config/android-v4"
SERIES_DETAIL_URL = "https://v.tenplay.com.au/api/videos/bcquery"
logger = logging.getLogger(__name__)

class TenMediaNode(AbstractNode):
    def __init__(self, title: str, video_url: str) -> None:
        super().__init__(title)

        # Ten is utterly broken at the moment. If I can't get it working with 
        # yt-dlp, it's not coming back at. Temporary fix to eliminate old downloader.
        # TODO Fix 10Play.
        self._media_url = video_url

    def _fill_children(self) -> None:
        """Load child nodes."""
        # Downloadable leaf. No children.
        self._children = []



class TenMediaContainerNode(AbstractNode):
    # TODO Fix up annotations if we keep this.
    def __init__(
        self, title: str, query: Any, expected_tv_show: Any
    ) -> None:
        super().__init__(title)
        self.title = title
        self.query = query
        self.expected_tv_show = expected_tv_show
        # TODO Fix up annotations if we keep this.
        self.video_ids: set[Any] = set()

    def _fill_children(self) -> None:
        self._children = []
        page_number = 0
        while page_number < 100:
            url = self.get_page_url(self.query, page_number)
            page_number += 1

            page = grab_json(url)
            items = page["items"]
            if len(items) == 0:
                break

            for video_desc in items:
                self.process_video(video_desc)

    # TODO Fix up annotations if we keep this.
    def get_page_url(self, query: Any, page_number: Any) -> Any:
        return (
            append_to_query_string(
                SERIES_DETAIL_URL,
                {
                    "command": "search_videos",
                    "page_size": "30",
                    "page_number": str(page_number),
                },
            )
            + query
        )

    # TODO Fix up annotations if we keep this.
    def process_video(self, video_desc: Any) -> None:
        video_id = video_desc["id"]
        video_url = video_desc["HLSURL"]
        tv_show = video_desc["customFields"]["tv_show"]
        title = video_desc["name"]

        if video_id in self.video_ids:
            return
        if tv_show != self.expected_tv_show:
            logger.warning(
                "Skipping unexpected video: %s != %s", tv_show, self.expected_tv_show
            )
            return
        self.video_ids.add(video_id)

        self._children.append(TenMediaNode(title, video_url))


class TenRootNode(AbstractNode):
    """Root node for Ten tree."""

    # __init__ from super class. Handle in pydantic in future.

    def _fill_children(self) -> None:
        """Create list of media containers."""
        doc = grab_json(SERIES_LIST_URL)

        self._children = []
        for series in doc["Browse TV"]["Shows"]:
            title = series["title"]
            query = series["query"] + series["episodefilter"]
            expected_tv_show = series["tv_show"]

        self._children.append(
            # Can fix annotation error by moving append into _fill_children.
            TenMediaContainerNode(title, query, expected_tv_show)
        )
