#!/usr/bin/env python3
# cspell:ignore delx webdl
"""Abstract Node base class for the tree of streaming services and their catalogues."""

from abc import ABC, abstractmethod
import logging
from subprocess import run as run_sub, SubprocessError

from webdl_reloaded.common import natural_sort, WebDLPaths

logger = logging.getLogger(__name__)


class AbstractNode(ABC):
    """Base class for walking streaming provider catalogues and download links.

    Not instantiable by design.
    """

    title: str
    # Removed parent attribute. Parents are responsible for tracking children, but
    # but not vice versa. I'm believe this will simplify handling of Nodes with
    # multiple parents - e.g. a series in multiple genres has only one instance, with
    # each genre keeping track of it as a child.
    _children: list[AbstractNode] | None
    # Media url has three states.
    # - None - for non-leaf nodes.
    # - "" - for leaf nodes that can lazy load media url via _get_media_url
    # - "<media url>" - leaf node media url after lazy load.
    # .can_download only check for leaf/non leaf distinction.
    # ._get_media_url performs lazy load if needed, and must be implemented by
    # leaf node classes.
    _media_url: str | None

    def __init__(self, title: str) -> None:
        """Initialise Node."""
        # Original webdl made child responsible for tracking its parent. I've
        # removed this and made parents responsible for tracking their children.
        self.title = title
        self._children = None
        self._media_url = None

    @property
    def can_download(self) -> bool:
        """Return True if node is downloadable."""
        if self._media_url is None:
            # Non leaf mode, not downloadable.
            return False
        # Downloadable leaf node.
        return True

    def _get_media_url(self) -> str:
        """Get media url attribute for downloader.

        Should be an empty string for all nodes except downloadable leaf nodes, which
        should overwrite this method.
        """
        # Media url should be None for everything other than downloadable
        # leaf nodes. AbstractNode provides a default yt-dlp downloader call which the
        # leaf node should overload/overwrite. This function should lazy load
        # media url if required.
        # See iView and SBS for sample leaf node implementations.

        # Most Nodes are not downloadable, and shouldn't call this. But
        # just in case!
        raise RuntimeError(
            f"Node '{self.title}' is not a downloadable node."
            f"  (_get_media_url() implementation missing?)."
        )

    @property
    def children(self) -> list[AbstractNode]:
        """Return list of all children of this Node."""
        # delx used to initialise with self.children=[]
        # and then fill children using:
        # if not self.children:
        #    self._fill_children()
        # This could result in multiple checks for Nodes with no children, and
        # I'm assuming it only needs checking once. So I'm defaulting children to None
        # and then initialising list in fill children.
        # Revert to delx approach if this breaks things.
        if self._children is None:
            # Children need to be lazy loaded.
            self._fill_children()
            # Check that _fill_children honoured the contract.
            # Explicit is better, overhead is minimal.
            if self._children is None:
                raise TypeError(
                    f"Invalid implementation of method AbstractNode._fill_children()!"
                    f"\n  '{self.__class__.__name__}._fill_children()' did not"
                    f" fill attribute self.children[AbstractNode]."
                    f"\n  (method should create empty list for media leaf node,"
                    f" or list of child nodes for branch nodes.)"
                )
            self._children = natural_sort(self._children, key=lambda node: node.title)
        return self._children

    @abstractmethod
    def _fill_children(self) -> None:
        """Fill the list child nodes for this node."""
        # Virtual method. Derived Nodes should create and fill
        # self.children[Node].
        # Downloadable leaf node should create self.children[] (empty list)
        raise NotImplementedError

    def add_child(self, child: AbstractNode) -> None:
        """Add child to the list of children."""
        # Add child re-enabled as it enables implementation of grandchildren nodes
        # for some cases.
        if self._children is None:
            self._children = []
        self._children.append(child)

    def download(self, paths: WebDLPaths, simulate: bool = False) -> bool:
        """Download file, return True on success."""
        if not self.can_download:
            # Most Nodes are not downloadable, and shouldn't call this. But
            # just in case!
            raise RuntimeError(
                f"Node '{self.title}' is not a downloadable node."
                f"  (download implementation missing?)."
            )

        media_url = self._get_media_url()

        args = [
            str(paths.yt_dlp_path),
            "--paths",
            str(paths.target_dir_path),
            "--output",
            f"{self.title}.%(ext)s",
        ]
        if paths.yt_dlp_conf_path:
            args.append("--config-locations")
            args.append(str(paths.yt_dlp_conf_path))

        args.append(media_url)

        if simulate:
            logger.info("Simulated Download: %s", self.title)
            return False

        try:
            run_sub(args=args, check=True)
        except SubprocessError as exc:
            logger.error("Download of file '%s' failed:\n   %s.", self.title, exc)
            return False

        return True
