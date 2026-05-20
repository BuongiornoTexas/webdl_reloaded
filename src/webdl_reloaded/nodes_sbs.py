#!/usr/bin/env python3
# cspell:ignore webdl
"""Provides media nodes for SBS on demand."""

import logging
from time import sleep

from typing import Optional

from pydantic import BaseModel

from webdl_reloaded.node import AbstractNode
from webdl_reloaded.common import append_to_query_string, grab_text

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


class CollectionMeta(BaseModel):
    """Collection metadata."""

    # Barely use this, but it still makes life easier.
    nextCursor: Optional[str] = None
    total: int


class SBSCatalogue(BaseModel):
    """Pydantic BaseModel for SBS collection."""

    items: list[SBSCatalogueItem]
    meta: CollectionMeta


class SBSEpisode(BaseModel):
    """Minimum data for generating media node."""

    title: str
    seasonNumber: int
    episodeNumber: int
    mpxMediaID: int


class SBSSeason(BaseModel):
    """SBS season, list of SBS episodes."""

    # While this could be done with a type adapter, pydantic docs suggests this
    # would be inefficient as the TypeAdapter would need to be constructed
    # each time it is used (each time a season is processed).
    episodes: list[SBSEpisode]


class SBSSeries(BaseModel):
    """SBS series, list of SBSSeasons."""

    # While this could be done with a type adapter, pydantic docs suggests this
    # would be inefficient as the TypeAdapter would need to be constructed
    # each time it is used (each time a series is processed).
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
            # It's a series. Construct the url, create the series and its episodes.
            series_text = grab_text(
                CATALOGUE_URL
                + SERIES_MAP[self.catalogue.entityType]
                + self.catalogue.slug
            )
            series_info = SBSSeries.model_validate_json(series_text)
            for season in series_info.seasons:
                for episode in season.episodes:
                    # Convert title to preferred format.
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
        # Note: an item is single instanced within a collection, but I don't bother
        # trying to single instance across collections (would require class variables
        # and considerable extra work). I suspect there won't be much in the way of
        # duplication and we can just live with the inefficiency of duplicated catalogue
        # items (doesn't affect functionality).
        self._children = []

        logger.info("Fetching '%s' catalogue.", self.collection)
        expect_count, items = self._fetch_collection()
        logger.info("  Expected '%s' item.", expect_count)
        logger.info("  Fetched '%s' items.", len(items))

        genre_map: dict[str, SBSGenreNode] = {}
        for catalog_item in items:
            # Append the very useful "All" to item genres.
            catalog_item.genres.append(ALL_BUCKET)
            # Create grandchild item container node.
            # (Path is collection->genre->item container)
            gc_container_node = SBSMediaContainerNode(
                catalog_item.title, catalogue=catalog_item
            )

            # Iterate over catalogue item genres and add the (single instance) of the
            # catalogue item to the corresponding genre node.
            for genre in catalog_item.genres:
                genre_node = genre_map.get(genre)
                if genre_node is None:
                    # Create genre, add as child node of this collection
                    # and update genre map.
                    genre_node = SBSGenreNode(genre)
                    self._children.append(genre_node)
                    genre_map[genre] = genre_node

                # Finally, because we have enough detail to be able to do so,
                # add the grandchild item container to the genre.
                # (Not as stupid as it looks - this approach allows single
                # instance of the container node to be shared with all genres
                # that it falls into.)
                genre_node.add_child(gc_container_node)

    def _fetch_collection(self) -> tuple[int, list[SBSCatalogueItem]]:
        """Fetch collection catalogue items as a JSON list."""
        base_url = COLLECTION_URL + self.collection
        items: list[SBSCatalogueItem] = []
        # First call, ask for max limit on items.
        url = append_to_query_string(base_url, {"limit": f"{MAX_ITEMS}"})
        while True:
            # Do request as text and then direct to pydantic rather than double handling
            # of request->json serialisation->pydantic base model.
            # Have I mentioned how much pydantic delights.
            catalogue = SBSCatalogue.model_validate_json(grab_text(url))
            items.extend(catalogue.items)
            cursor = catalogue.meta.nextCursor
            if cursor is None:
                break
            # Don't hammer the API
            sleep(0.2)
            # Set up next batch
            url = append_to_query_string(base_url, {"cursor": cursor})

        return (catalogue.meta.total, items)


class SbsRootNode(AbstractNode):
    """Root node for SBS tree."""

    # __init__ from super class. Handle in pydantic in future.

    def _fill_children(self) -> None:
        """Fill SBS media types."""
        self._children = []
        for title, collection in COLLECTION_MAP.items():
            self._children.append(SBSTypeNode(title, collection))
