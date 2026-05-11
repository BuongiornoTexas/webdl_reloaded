#!/usr/bin/env python3
# cspell:ignore webdl
"""Provides media nodes for SBS on demand."""

import logging
from time import sleep

# TODO Sort out JSON annotation and remove ANY
from typing import Any, Optional

from pydantic import BaseModel

from webdl_reloaded.node import AbstractNode
from webdl_reloaded.common import append_to_query_string
from webdl_reloaded.old_common import grab_json

logger = logging.getLogger(__name__)

# Dummy bucket to catch all shows/programs in. Useful for batch mode.
ALL_BUCKET = "All"
SBS_ID = "SBS"
CATALOGUE_URL = "https://catalogue.pr.sbsod.com/"
COLLECTION_URL = CATALOGUE_URL + "collections/"
DOWNLOAD_URL = "https://www.sbs.com.au/ondemand/watch/"
# As of 5/5/26, max items per catalogue call is 100
MAX_ITEMS = 100
# Map media types to SBS collections.
COLLECTION_MAP = {
    "TV Shows": "all-tv-shows",
    "Movies": "all-movies",
    "Sports": "browse-all-sport",
    "News": "news-and-current-affairs-tv-shows",
}
# This one is a bit messy. key: value pairs are;
#    entityType = series_prefix
#       series_prefix is an empty string a single episode show or movie.
#       series_prefix is the url prefix for the entity type otherwise.
SERIES_MAP = {
    "TV_SERIES": "tv-series/",
    "NEWS_SERIES": "news-series/",
    "SPORTS_SERIES": "sports-series/",
}


class SBSCatalogueItem(BaseModel):
    """Pydantic BaseModel for all of the data we need from catalogue items."""

    # Pydantic is monster overkill, but also so easy!
    entityType: str
    title: str
    slug: str
    mpxMediaID: Optional[int] = None
    genres: list[str]


class SBSEpisode(BaseModel):
    """Minimum data for generating media node."""

    title: str
    seasonNumber: int
    episodeNumber: int
    mpxMediaID: int


class SBSSeason(BaseModel):
    """SBS season, list of SBS episodes."""

    episodes: list[SBSEpisode]


class SBSSeries(BaseModel):
    """SBS series, list of SBSSeasons."""

    seasons: list[SBSSeason]


class SBSMediaNode(AbstractNode):
    """Downloadable SBS media node."""

    _mpx_media_id: str

    def __init__(self, title: str, mpx_media_id: int) -> None:
        """Initialise container node."""
        super().__init__(title)

        # Downloadable, so need non-empty _media_url to enable lazy load
        self._media_url = ""

        # Store for lazy load.
        self._mpx_media_id = str(mpx_media_id)

    def _get_media_url(self) -> str:
        """Return media url. Lazy load if needed."""
        if self._media_url:
            # Loaded previously. Return value.
            return self._media_url

        # Much like ABC, it looks as yt-dlp can get everything it needs for SBS from
        # a simple url (subs, images, etc.), so not much of a lazy load.
        self._media_url = DOWNLOAD_URL + self._mpx_media_id
        return self._media_url

    def _fill_children(self) -> None:
        self._children = []


class SBSMediaContainerNode(AbstractNode):
    """SBS media container node."""

    catalogue: SBSCatalogueItem

    def __init__(self, title: str, catalogue: SBSCatalogueItem) -> None:
        """Initialise container node."""
        super().__init__(title)

        self.catalogue = catalogue

    def _fill_children(self) -> None:
        self._children = []
        if self.catalogue.mpxMediaID:
            # It's a single show/program/movie. Add the only downloadable.
            title = self.title + f" ({SBS_ID})"
            self._children.append(SBSMediaNode(title, self.catalogue.mpxMediaID))
        else:
            # It's a series. Construct the url and make it happen.
            series_json = grab_json(
                CATALOGUE_URL
                + SERIES_MAP[self.catalogue.entityType]
                + self.catalogue.slug
            )
            series_info = SBSSeries.model_validate(series_json)
            for season in series_info.seasons:
                for episode in season.episodes:
                    title = (
                        f"{self.title}"
                        f" S{episode.seasonNumber}E{episode.episodeNumber:02d}"
                        f" {episode.title}"
                        f" ({SBS_ID})"
                    )

                    self._children.append(
                        SBSMediaNode(title=title, mpx_media_id=episode.mpxMediaID)
                    )


class SBSGenreNode(AbstractNode):
    """SBS genre node."""

    def _fill_children(self) -> None:
        # Shouldn't be called. Genre children are added by self.add_child
        if self._children is None:
            self._children = []


class SBSTypeNode(AbstractNode):
    """SBS media type node."""

    collection: str

    def __init__(self, title: str, collection: str):
        """Initialise media type node."""
        super().__init__(title)
        self.collection = collection

    def _fill_children(self) -> None:
        self._children = []

        logger.info("Fetching '%s' catalogue.", self.collection)
        expect_count, items = self._fetch_json_items()
        logger.info("  Expect '%s' item.", expect_count)
        logger.info("  Fetched %s items.", len(items))

        genre_map: dict[str, SBSGenreNode] = {}
        for item_json in items:
            catalog_item = SBSCatalogueItem.model_validate(item_json)
            # Create item container node.
            container_node = SBSMediaContainerNode(
                catalog_item.title, catalogue=catalog_item
            )

            # Add the catch all genre.
            catalog_item.genres.append(ALL_BUCKET)
            for genre in catalog_item.genres:
                genre_node = genre_map.get(genre)
                if genre_node is None:
                    # Create genre child node and update genre map.
                    genre_node = SBSGenreNode(genre)
                    self._children.append(genre_node)
                    genre_map[genre] = genre_node

                # Finally, because we have enough detail to be able to so,
                # add the grandchild container to the genre.
                # (Not as stupid as it looks - this approach allows single
                # instance of the container node to be shared with all genres
                # that it falls into.)
                genre_node.add_child(container_node)

    # TODO Fix JSON collection annotation
    def _fetch_json_items(self) -> tuple[int, Any]:
        """Fetch collection catalogue items as a JSON list."""
        items = []
        # First call, ask for max limit on items.
        url = append_to_query_string(COLLECTION_URL + self.collection, {
            "limit": f"{MAX_ITEMS}"
        })
        while True:
            data = grab_json(url)
            items.extend(data["items"])
            cursor = data["meta"].get("nextCursor")
            if cursor is None:
                break
            # Don't hammer the API
            sleep(0.2)
            # Set up next batch
            url = append_to_query_string(
                COLLECTION_URL + self.collection, {"cursor": cursor}
            )

        expect_count = int(data["meta"]["total"])
        return (expect_count, items)


class SbsRootNode(AbstractNode):
    """Root node for SBS tree."""

    # __init__ from super class. Handle in pydantic in future.

    def _fill_children(self) -> None:
        """Fill SBS media types."""
        self._children = []
        for title, collection in COLLECTION_MAP.items():
            self._children.append(SBSTypeNode(title, collection))
