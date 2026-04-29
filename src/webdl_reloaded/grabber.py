#!/usr/bin/env python3
# cspell:ignore rsrtools
"""A simple interactive system for selecting and downloading FTA media."""
from typing import cast
from node import Node
from common import natural_sort
from node_fta_services import FTAServices


def choose(options: list[tuple[str, Node]], allow_multi: bool) -> None | list[Node]:
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
    print("  0) Back")
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
                reverse_map[value] for value in values if value in reverse_map
            ]
            if allow_multi or len(ret_values) == 1:
                return ret_values

        except (ValueError, IndexError):
            print("Invalid input, please try again")


def main() -> None:
    """Provide interactive selection for media downloads."""
    node = cast(Node, FTAServices())

    while True:
        menu_options = []
        download_enabled = True
        for n in node.children:
            menu_options.append((n.title, n))
            if not n.can_download:
                # root or navigation node, not downloadable.
                download_enabled = False
        menu_options = natural_sort(menu_options, key=lambda x: x[0])
        # If we are at the episode/movie level that allows downloading, we can
        # select multiples (download_enabled == True enables multi-select).
        selected_nodes = choose(menu_options, allow_multi=download_enabled)
        if selected_nodes is None:
            if node.parent is not None:
                node = node.parent
            else:
                break
        elif download_enabled:
            for n in selected_nodes:
                if not n.download():
                    input("Press return to continue...\n")
        else:
            if len(selected_nodes) != 1:
                # Should only return 1 node selection if not downloading.
                raise IndexError("Unexpected multiple index/root nodes returned.")
            node = selected_nodes[0]


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting...")
