#!/usr/bin/env python3
# cspell:ignore rsrtools autograbber webdl
"""A simple interactive system for selecting and downloading FTA media."""

from typing import cast

from webdl_reloaded.common import natural_sort, process_args
from webdl_reloaded.node import AbstractNode
from webdl_reloaded.node_services import ServiceProviders


def choose(
    options: list[tuple[str, AbstractNode]], allow_multi: bool
) -> None | list[AbstractNode]:
    """Provide a very basic interactive text menu system for user input."""
    # TODO: Upgrade with enhanced choose from sleeper_service/rsrtools.
    #       Right now I've made typing consistent with way choose is applied.
    #       From my memory, my updated version offers a bit more flex, and ?may?
    #       be cleaner?
    reverse_map = {}
    for i, (key, value) in enumerate(options):
        # Create the selection menu.
        print(f"{i+1:4}) {key}")
        reverse_map[i + 1] = value
    print("   0) Back")
    while True:
        try:
            str_values = input("Choose> ").split()
            if len(str_values) == 0:
                continue
            if "0" in str_values:
                return None
            values = []
            for s in str_values:
                # Convert string return into one or more integer values.
                if s.isdigit():
                    values.append(int(s))
                else:
                    low, high = s.split("-", 1)
                    values.extend(range(int(low), int(high) + 1))
            ret_values = [
                # Generate selection from integer indices.
                reverse_map[value]
                for value in values
                if value in reverse_map
            ]
            if allow_multi or len(ret_values) == 1:
                return ret_values

        except ValueError, IndexError:
            print("Invalid input, please try again")


def main() -> None:
    """Provide interactive selection for media downloads."""
    settings = process_args()

    path_info = None
    for path_info in settings.webdl_paths():
        # grabber downloads to the first available path.
        break
    if not path_info:
        print(
            "No target directory found check command line and 'webdl.toml'. "
        )
        print("Exiting.")
        return

    active_node = cast(AbstractNode, ServiceProviders("Services"))

    # Keep track of where we are in the tree with an array (autograbber does
    # this with recursion).
    node_path: list[AbstractNode] = []
    while True:
        menu_options = []
        download_enabled = True
        for node in active_node.children:
            menu_options.append((node.title, node))
            if not node.can_download:
                # root or navigation node, not downloadable.
                download_enabled = False
        menu_options = natural_sort(menu_options, key=lambda x: x[0])
        # If we are at the episode/movie level that allows downloading, we can
        # select multiples (download_enabled == True enables multi-select).
        selected_nodes = choose(menu_options, allow_multi=download_enabled)
        if selected_nodes is None:
            if len(node_path) == 0:
                # At the root node. Nothing more to do.
                break
            # Otherwise, move one node closet to the root and continue.
            active_node = node_path.pop()
        elif download_enabled:
            # Don't need to do anything with the node path.
            for node in selected_nodes:
                if not node.download(path_info):
                    input("Press return to continue...\n")
        else:
            if len(selected_nodes) != 1:
                # Should only return 1 node selection if not downloading.
                raise IndexError("Unexpected multiple index/root nodes returned.")
            # push current node onto path and make selected node active.
            node_path.append(active_node)
            active_node = selected_nodes[0]


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt, EOFError:
        print("\nExiting...")
