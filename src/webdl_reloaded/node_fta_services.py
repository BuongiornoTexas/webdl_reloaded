#!/usr/bin/env python3
# cspell:ignore iview, webdl
"""Root node for the tree, contains all FTA streaming service provider root nodes.

Replaces webdl.common.load_root_node method and is more consistent with other node
classes/objects.
"""

from node import Node
# Each new service needs to be added here and called in _fill_children
from nodes_iview import IviewRootNode
from nodes_sbs import SbsRootNode
from nodes_ten import TenRootNode


class FTAServices(Node):
    """Root node for streaming service providers."""

    def __init__(self) -> None:
        """Initialise service providers."""
        super().__init__(title="Services", parent=None)

    def _fill_children(self) -> None:
        """Add all service provider root nodes."""
        IviewRootNode(self)
        SbsRootNode(self)
        TenRootNode(self)
