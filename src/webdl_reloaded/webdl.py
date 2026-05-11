#!/usr/bin/env python3
# cspell:ignore webdl, autograbber
"""Entry point for webdl_reloaded.

A simple interactive system for selecting and downloading FTA media.
"""

from webdl_reloaded.common import process_args
from webdl_reloaded.grabber import grabber
from webdl_reloaded.autograbber import autograbber

if __name__ == "__main__":
    # TODO Add command line option to specify debug level.
    # TODO Add command line to specify logfile location (batch mode only?).
    settings = process_args()

    try:
        if settings.interactive:
            grabber(settings)
        else:
            autograbber(settings)
    except KeyboardInterrupt, EOFError:
        print("\nExiting...")
