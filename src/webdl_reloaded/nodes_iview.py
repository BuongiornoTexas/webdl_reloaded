#!/usr/bin/env python3
# cspell:ignore iview webdl
"""Provides media nodes for ABC iView."""

import logging

from typing import Optional

from pydantic import BaseModel, Field, AliasChoices, Json

from webdl_reloaded.node import AbstractNode
from webdl_reloaded.common import grab_text, standardize_title

ABC_ID = "ABC"
IVIEW_ID = "ABC iView"
BASE_URL = "https://iview.abc.net.au/"
VIDEO_URL = BASE_URL + "/video/"
API_URL = "https://iview.abc.net.au/api/"

ALL_BUCKET = "All"
ALL_HREF = ""

logger = logging.getLogger(__name__)


class SeriesModel(BaseModel):
    """Series information."""

    seriesTitle: str
    latestEpisode: str


class SeriesListModel(BaseModel):
    """List of Series."""

    # Use Json type to allow string coercion within in pydantic. A bit
    # yuck, but better than doing the iterations myself.
    seriesList: Json[list[SeriesModel]]


class EpisodeModel(BaseModel):
    """Episode data model."""

    # I think this is all we need. It's possible episodeTitle may not always
    # appear. In which case, treat this as Optional and handle the special case
    # in SeriesNode.
    seriesTitle: str
    # ABC is inconsistent about this element.
    title: Optional[str] = None
    episodeHouseNumber: str
    href: str


class EpisodesListModel(BaseModel):
    """Collection of episode models."""

    episodes: list[EpisodeModel]


class CollectionsModel(BaseModel):
    """Collections/index/carousels."""

    carousels: list[EpisodesListModel]
    collections: list[EpisodesListModel]
    index: list[EpisodesListModel]


class CategoryModel(BaseModel):
    """Category data for channels and genres."""

    title: str
    href: str


class CategoriesListModel(BaseModel):
    """Collection of category (genre) models."""

    categories: list[CategoryModel] = Field(
        validation_alias=AliasChoices("channels", "categories")
    )


class MediaNode(AbstractNode):
    """Downloadable iView media (episode) Node."""

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


class SeriesNode(AbstractNode):
    """Container for episodes."""

    # Fortunately, iView treats EVERYTHING as a series.
    # This is the MediaContainerNode for iView.
    _slug: str

    def __init__(self, title: str, slug: str) -> None:
        """Initialise iView series node."""
        super().__init__(title)
        self._slug = slug

    def _fill_children(self) -> None:
        self._children = []

        # Grab the series info.
        # Most typical container for iView media Nodes.
        text = grab_text(API_URL + "series/" + self._slug)
        data = EpisodesListModel.model_validate_json(text)

        for episode in data.episodes:
            # video_key = episode["episodeHouseNumber"]
            # series_title = episode["seriesTitle"]
            # episode_title = episode.get("title", None)

            title = episode.seriesTitle
            if episode.title:
                title += " " + episode.title
            else:
                logger.debug(
                    "Episode without title (movie, trailer, etc.): %s (%s)",
                    title,
                    episode.episodeHouseNumber,
                )

            title = standardize_title(title, ABC_ID)

            self._children.append(MediaNode(title, episode.episodeHouseNumber))


class CategoryNode(AbstractNode):
    """Channels and genres, includes an "All". Container for Series."""

    _href: str
    # Class variable to gather all series nodes. Key is series slug.
    _series_map: dict[str, SeriesNode] = {}

    def __init__(self, title: str, href: str) -> None:
        """Initialise instance."""
        super().__init__(title)
        self._href = href

    @staticmethod
    def _get_series_slug(href: str) -> str:
        """Extract series slug from href."""
        return href.split("/")[1].strip()

    @classmethod
    def _fill_series_map(cls) -> None:
        """Pull series info from ABC and create unique series map."""
        logger.info("Pulling iView series list.")
        text = grab_text(API_URL + "series")
        # mypy doesn't understand that pydantic knows how to deal with this coercion
        # correctly.
        data = SeriesListModel(seriesList=text)  # type: ignore

        base_map: dict[str, list[str]] = {}
        # Messy & inefficient two pass process to ensure unique titles.
        # I'm assuming slugs are unique!
        for series in data.seriesList:
            title = series.seriesTitle
            this_slug = cls._get_series_slug(series.latestEpisode)
            if title not in base_map:
                base_map[title] = [this_slug]
            else:
                base_map[title].append(this_slug)

        # Now create uniquely named series map.
        for title, slugs in base_map.items():
            if len(slugs) == 1:
                cls._series_map[slugs[0]] = SeriesNode(title, slugs[0])
            else:
                # I strongly suspect this will never ever be triggered.
                for i, slug in enumerate(slugs):
                    cls._series_map[slug] = SeriesNode(f"{title} ({i+1})", slug)

    def _fill_children(self) -> None:
        """Fill series in category, including "All"."""
        if not self._series_map:
            # Grab the master list of series.
            self._fill_series_map()

        if self.title == ALL_BUCKET and self._href == ALL_HREF:
            # Special snowflake.
            self._children = list(self._series_map.values())
            return

        # Actual ABC collection.
        # Only create one entry for each series, even if it occurs multiple times.
        unique_series = set()
        self._children = []
        text = grab_text(API_URL + self._href)
        data = CollectionsModel.model_validate_json(text)
        for collection_list in [data.carousels, data.index, data.collections]:
            for collection in collection_list:
                for series in collection.episodes:
                    # We should have an episode from a series now.
                    slug = self._get_series_slug(series.href)
                    if slug not in unique_series:
                        # Skip repeats.
                        unique_series.add(slug)
                        if node := self._series_map.get(slug):
                            # Found something on the A-Z program list
                            self._children.append(node)
                        else:
                            # Not on the A-Z program list, but still something
                            # (e.g. preview, coming soon, etc.). Add and kick
                            # down the road.
                            self._children.append(SeriesNode(series.seriesTitle, slug))


class CategoriesListNode(AbstractNode):
    """Container for lists of categories (e.g. channels, categories)."""

    def _fill_children(self) -> None:
        """Create category list."""
        if self.title == ALL_BUCKET:
            # Special case of ABC iView/All/All
            self._children = [CategoryNode(ALL_BUCKET, ALL_HREF)]
            return

        logger.info("Fetching iView '%s' catalogue.", self.title)
        text = grab_text(API_URL + self.title.lower())
        logger.info("Processing iView '%s' catalogue.", self.title)
        data = CategoriesListModel.model_validate_json(text)

        # Create list and the catch all.
        self._children = [CategoryNode(ALL_BUCKET, ALL_HREF)]
        # Annoyingly, ABC names the categories so we need two levels of
        # dereference to get to the list.
        for category in data.categories:
            self._children.append(CategoryNode(category.title, category.href))


class IViewRootNode(AbstractNode):
    """Root node for iView tree."""

    def _fill_children(self) -> None:
        self._children = [
            CategoriesListNode("Categories"),
            CategoriesListNode("Channels"),
            # Deal with the special.
            CategoriesListNode(ALL_BUCKET),
            # Dropping featured altogether. It really doesn't add value.
        ]
