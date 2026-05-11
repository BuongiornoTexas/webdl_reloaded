#!/usr/bin/env python3
# cspell:ignore iview, webdl
"""Root node for the tree, contains all FTA streaming service provider root nodes.

Replaces webdl.common.load_root_node method and is more consistent with other node
classes/objects.

Suggested naming convention for service provider subclasses, using iView as an
example.

- IViewNode - virtual node if needed.
- IViewRootNode - root of provider tree. May do a lot of the heavy lifting in process
provider api.
- IViewIndexNode - general navigation node.
- IViewMediaContainerNode - container for downloadable media node if different from
general index node.
- IViewMediaNode - Leaf node for downloadable media, knows how to download itself, has
no children.
"""

from webdl_reloaded.node import AbstractNode
from webdl_reloaded.nodes_iview import IVIEW_ID, IViewRootNode
from webdl_reloaded.nodes_sbs import SBS_ID, SbsRootNode
from webdl_reloaded.nodes_ten import TEN_ID, TenRootNode

# Each new service needs to be added here and called in _fill_children
SERVICE_PROVIDERS: dict[str, type[AbstractNode]] = {
    IVIEW_ID: IViewRootNode,
    SBS_ID: SbsRootNode,
    # Ten is not browseable past the root node.
    TEN_ID: TenRootNode,
}


class ServiceProviders(AbstractNode):
    """Root node for streaming service providers."""

    def _fill_children(self) -> None:
        """Add all service provider root nodes."""
        self._children = []
        for title, node_class in SERVICE_PROVIDERS.items():
            self.children.append(node_class(title))
