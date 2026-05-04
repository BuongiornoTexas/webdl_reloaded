#!/usr/bin/env python3
# cspell:ignore delx
"""Abstract Node base class for the tree of streaming services and their catalogues."""
from abc import ABC, abstractmethod
from common import natural_sort


class AbstractNode(ABC):
    """Base class for walking streaming provider catalogues and download links.

    Not instantiable by design.
    """

    title: str
    parent: AbstractNode | None
    _children: list[AbstractNode] | None = None
    can_download: bool = False

    def __init__(self, title: str, parent: AbstractNode | None = None) -> None:
        """Initialise Node."""
        # Original webdl made child responsible for tracking its parent. I've 
        # removed this and made parents responsible for tracking their children. 
        self.title = title
        self.parent = parent

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

    # add_child disabled for now, as children should be created in _fill_children
    # def add_child(self, child: AbstractNode) -> None:
    #    """Add child to the list of children."""
    #    if self._children is None:
    #        self._children = []
    #    self._children.append(child)

    def download(self) -> bool:
        """Download file if possible.

        Most Nodes are not downloadable, so the default implementation is a to
        raise RunTimeError. Downloadable nodes should a) implement the download and
        return True on success and b) set the self.can_download flag to True.
        """
        raise RuntimeError(f"Node {self.title} is not downloadable.")
