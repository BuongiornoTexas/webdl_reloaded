#!/usr/bin/env python3
# cspell:ignore autograbber webdl
"""Implements the batch media downloader (autograbber)."""

import logging

from pathlib import Path
from fnmatch import fnmatch

from webdl_reloaded.common import process_args, WebDLPaths
from webdl_reloaded.node import AbstractNode
from webdl_reloaded.node_services import ServiceProviders

HISTORY_FILENAME = ".history.txt"
PATTERN_FILENAME = ".patterns.txt"
EXCLUDE_FILENAME = ".excludes.txt"
DEFAULT_ENCODING = "utf-8"
LOGFILE = "autograbber.log"
logger = logging.getLogger(__name__)


class DownloadList:
    """Class to manage download history and download exclusions."""

    _target_dir_path: Path
    _history_file: Path
    exclude_list: set[str]
    seen_list: set[str]

    def __init__(self, target_dir_path: Path) -> None:
        """Initialise instance, read download history and exclusions."""
        self._target_dir_path = target_dir_path
        self.exclude_list = set()
        self.seen_list = set()

        self._load_exclude_list()

        self._load_history_file()

    def _load_exclude_list(self) -> None:
        """Load exclusion list."""
        try:
            exclusion_file = self._target_dir_path / EXCLUDE_FILENAME
            with open(exclusion_file, "r", encoding=DEFAULT_ENCODING) as exclude:
                for line in exclude:
                    self.exclude_list.add(line.strip())
        except FileNotFoundError:
            # Exclusion file is optional.
            pass

    def _load_history_file(self) -> None:
        """Read history file into check list."""
        # Note: removed support for old downloaded_auto.text files.
        try:
            self._history_file = self._target_dir_path / HISTORY_FILENAME
            with open(self._history_file, "r", encoding=DEFAULT_ENCODING) as history:
                for line in history:
                    self.seen_list.add(line.strip())
        except FileNotFoundError:
            # No history, so we will create it later.
            pass
        except Exception as exc:
            logger.error(
                "Error reading history file: %s -- %s.", self._history_file, exc
            )
            raise

    def pending(self, node: AbstractNode) -> bool:
        """Determine if node media should be downloaded based on history and exclusions.

        Returns false if node.title:
            - Appears in the history list (already downloaded).
            - Is in the exclusion list (should not be downloaded).
        """
        title = node.title.strip()
        if title in self.seen_list:
            return False
        for exclude in self.exclude_list:
            if fnmatch(title, exclude):
                return False
        return True

    def add_to_history(self, node: AbstractNode) -> None:
        """Add title to history file and seen list."""
        self.seen_list.add(node.title.strip())
        # This is not efficient, as we add a line at a time. But often
        # won't add any on any given batch run. I'd rather do this than keep a file
        # pointer dangling in the class.
        with open(self._history_file, "a", encoding=DEFAULT_ENCODING) as history:
            history.write(node.title.strip() + "\n")


class DownLoader:
    """Minimal pattern match downloader.

    This is really a glorified call to the old webdl "match & download" method.
    Converted to a class to make calling mechanics and recursion cleaner.
    """

    _download_list: DownloadList
    _path_info: WebDLPaths

    def __init__(self, path_info: WebDLPaths) -> None:
        """Initialise Downloader."""
        self._path_info = path_info
        self._download_list = DownloadList(path_info.target_dir_path)

    def download_matches(self, node: AbstractNode, pattern: list[str]) -> None:
        """Perform sanity checks and run the match and download."""
        if len(pattern) == 0 or pattern is None:
            # No match possible.
            return

        # Do the actual download and match by private method.
        # Note: index should not be specified in this call.
        self._download_matches(node, pattern)

    def _download_matches(
        self, node: AbstractNode, pattern: list[str], index: int = 0
    ) -> None:
        """Walk the node tree and download matching media matching pattern.

        Node title is checked against pattern[index]. If a match occurs and node is:
            - A leaf node, downloaded the matched media and return.
            - A branch node, increment index and walk node's children.
        **This is the webdl match function with safety rails.**
        """
        if index >= len(pattern):
            # No more pattern elements to check, match failed.
            return

        if not fnmatch(node.title, pattern[index]):
            # Node does not match pattern, so end walk.
            return

        # Node title matches pattern[index]
        if node.can_download:
            # Node is a downloadable leaf.
            if self._download_list.pending(node):
                # Node hasn't been downloaded previously, and it's not on the
                # exclusion list. So we try to download.
                if node.download(self._path_info):
                    # Download succeeded, update history.
                    self._download_list.add_to_history(node)
                else:
                    # Download failed, update log.
                    logger.error("Failed to download! '%s'", node.title)
            # Regardless of download outcome, we are at a leaf node, and can't
            # walk the tree any deeper. So we return.
            return

        # Not a leaf node, but we did match the pattern.
        # So increment count and recurse to children.
        child_index = index + 1
        if child_index >= len(pattern):
            # No more pattern elements to check. We're done here.
            return

        for child in node.children:
            # Recurse to each child and check the next part of the pattern.
            self._download_matches(child, pattern, child_index)


def process_dir(path_info: WebDLPaths, pattern_file: Path) -> None:
    """Process the pattern file for a single download directory."""
    logger.info("Started %s", path_info.target_dir_path)
    services_root = ServiceProviders("Services")
    downloader = DownLoader(path_info)

    with open(pattern_file, "r", encoding=DEFAULT_ENCODING) as pattern_fp:
        for line in pattern_fp:
            # User supplied patterns don't include information about services_root
            # root node (it is internal to webdl).
            # So we run the pattern match against each of the children of services_root
            # (the services themselves).
            pattern = line.strip().split("/")
            for service in services_root.children:
                downloader.download_matches(service, pattern)

    logger.info("Finished '%s'", path_info.target_dir_path)


def main() -> None:
    """Run the batch job."""
    # Setup logger. Use force to override the basicConfig setup in common.py.
    # Doing this because autograbber is intended for batch mode and should
    # generate a logfile for after the event troubleshooting.
    # Location defaults to cwd(), file replaced each run.
    # Logs to file and console.
    logging.basicConfig(
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGFILE, mode="w", encoding=DEFAULT_ENCODING),
        ],
        force=True,
        level=logging.INFO,
    )

    settings = process_args()

    # Process each batch directory in turn.
    for path_info in settings.webdl_paths():
        pattern_path = path_info.target_dir_path / PATTERN_FILENAME
        if not pattern_path.is_file():
            logger.error("Pattern file '%s' missing. Skipping directory!", pattern_path)
            continue

        process_dir(path_info, pattern_path)


if __name__ == "__main__":
    # TODO Add command line option to specify debug level.
    # TODO Add command line to specify logfile location.

    try:
        main()
    except KeyboardInterrupt, EOFError:
        logger.info("\nExiting...")
