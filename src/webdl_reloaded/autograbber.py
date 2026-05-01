#!/usr/bin/env python3
# cspell:ignore autograbber webdl
"""Implements the batch media downloader (autograbber)."""

import logging
# TODO Clean up sys import after adding argparser and checking if sys.exit(1) needed.
import sys
from os import chdir
from pathlib import Path
from fnmatch import fnmatch
from node import Node
from node_fta_services import FTAServices

HISTORY_FILENAME = ".history.txt"
PATTERN_FILENAME = ".patterns.txt"
EXCLUDE_FILENAME = ".excludes.txt"
DEFAULT_ENCODING = "utf-8"
LOGGER = "autograbber"
LOGFILE = LOGGER + ".log"
logger = logging.getLogger(LOGGER)


class DownloadList():
    """Class to manage download history and download exclusions."""

    exclude_list: set = set()
    seen_list: set = set()

    def __init__(self) -> None:
        """Initialise instance, read download history and exclusions."""
        self._load_exclude_list()

        self._load_history_file()

    def _load_exclude_list(self) -> None:
        """Load exclusion list."""
        try:
            with open(EXCLUDE_FILENAME, "r", encoding=DEFAULT_ENCODING) as exclude:
                for line in exclude:
                    self.exclude_list.add(line.strip())
        except FileNotFoundError:
            # Exclusion file is optional.
            pass

    def _load_history_file(self) -> None:
        """Read history file into check list."""
        # Note: removed support for old downloaded_auto.text files.
        try:
            with open(HISTORY_FILENAME, "r", encoding=DEFAULT_ENCODING) as history:
                for line in history:
                    self.seen_list.add(line.strip())
        except FileNotFoundError:
            # No history, so we will create it later.
            pass
        except Exception as exc:
            logger.error("Error reading history file: %s -- %s.", HISTORY_FILENAME, exc)
            raise

    def pending(self, node: Node) -> bool:
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

    def add_to_history(self, node: Node) -> None:
        """Add title to history file and seen list."""
        self.seen_list.add(node.title.strip())
        # This is not efficient, as we add a line at a time. But often
        # won't add any on any given batch run. I'd rather do this than keep a file
        # pointer dangling in the class.
        with open(HISTORY_FILENAME, "a", encoding=DEFAULT_ENCODING) as history:
            history.write(node.title.strip() + "\n")


class DownLoader():
    """Minimal pattern match downloader.

    This is really a glorified call to the old webdl "match & download" method.
    Converted to a class to make calling mechanics and recursion cleaner.
    """

    download_list: DownloadList

    def __init__(self, download_list: DownloadList) -> None:
        """Initialise Downloader."""
        self.download_list = download_list

    def download_matches(self, node: Node, pattern: list[str]) -> None:
        """Perform sanity checks and run the match and download."""
        if len(pattern) == 0 or pattern is None:
            # No match possible.
            return

        # Do the actual download and match by private.
        # Note: index should not be specified in this call.
        self._download_matches(node, pattern)

    def _download_matches(self, node: Node, pattern: list[str], index: int = 0) -> None:
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
            if self.download_list.pending(node):
                # Node hasn't been downloaded previously, and it's not on the
                # exclusion list. So we try to download.
                if node.download():
                    # Download succeeded, update history.
                    self.download_list.add_to_history(node)
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


def process_one_dir(dest_dir: Path, pattern_file: Path) -> None:
    """Process the pattern file for a single download directory."""
    chdir(dest_dir)

    logger.info("Started %s", dest_dir)
    services_root = FTAServices()
    downloader = DownLoader(DownloadList())

    with open(pattern_file, "r", encoding=DEFAULT_ENCODING) as pattern_fp:
        for line in pattern_fp:
            # User supplied patterns don't include information about services_root
            # root node (it is internal to webdl).
            # So we run the pattern match against each of the children of services_root
            # (the services themselves).
            pattern = line.strip().split("/")
            for service in services_root.children:
                downloader.download_matches(service, pattern)

    logger.info("Finished '%s'", dest_dir)


def process_all_directories(download_dirs: list[str]) -> None:
    """Process each batch directory in turn."""
    for str_path in download_dirs:
        target_path = Path(str_path).resolve()
        logger.info("Checking target directory: '%s'", target_path)
        if not target_path.is_dir():
            logger.error("`'%s'` is not a directory. Skipping!", target_path)
            continue

        pattern_path = target_path / PATTERN_FILENAME
        if not pattern_path.is_file():
            logger.error("Pattern file '%s' missing file. Skipping!", pattern_path)
            continue

        process_one_dir(target_path, pattern_path)


if __name__ == "__main__":
    # TODO Implement arg_parser and options file (store yt-dlp and ffmpeg options!).
    # TODO Add command line option to specify debug level.
    # TODO Add command line to specify logfile location.
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

    if len(sys.argv) <= 1:
        logger.error("Usage: %s download_dir [download_dir ...]", sys.argv[0])
        sys.exit(1)

    try:
        process_all_directories(sys.argv[1:])
    except KeyboardInterrupt, EOFError:
        logger.info("\nExiting...")
