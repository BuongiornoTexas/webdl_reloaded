#!/usr/bin/env python3
# cspell:ignore delx
"""Node base class for the tree of streaming services and their catalogues."""

from common import natural_sort


class Node():
    """Base class for walking streaming provider catalogues and download links."""

    title: str
    parent: Node | None
    _children: list[Node] | None = None
    can_download: bool = False

    def __init__(self, title: str, parent: Node | None = None) -> None:
        """Initialise Node."""
        self.title = title
        if parent:
            # Need to add self to the parent's children.
            parent.add_child(self)
        self.parent = parent

    @property
    def children(self) -> list[Node]:
        """Return list of all children of this node."""
        # delx used to initialise with self.children=[]
        # and then fill children using:
        # if not self.children:
        #    self._fill_children()
        # This could result in multiple checks for nodes with no children, and
        # I'm assuming it only needs checking once. So I'm defaulting children to None
        # and then initialising list in fill children.
        # Revert to delx approach if this breaks things.
        if self._children is None:
            # Children need to be lazy loaded.
            self._fill_children()
            self._children = natural_sort(self._children, key=lambda node: node.title)
        return self._children

    def _fill_children(self) -> None:
        """Fill the list child nodes for this node."""
        # Base class implements a leaf node with no children. So returns an empty list.
        # Child classes should override this method if they have child nodes.
        if self._children is None:
            self._children = []

    def add_child(self, child: Node) -> None:
        """Add child to the list of children."""
        if self._children is None:
            self._children = []
        self._children.append(child)

    def download(self) -> bool:
        """Download file if possible.

        Most Nodes are not downloadable, so the default implementation is a to raise
        a RunTimeError. Downloadable nodes should a) implement the download and return
        True on success and b) set the self.can_download flag to True.
        """
        raise RuntimeError(f"Node {self.title} is not downloadable.")
