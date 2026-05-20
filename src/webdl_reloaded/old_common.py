#!/usr/bin/env python3
# cspell:ignore webdl autosocks
# Contains original webdl code still waiting on cleanup.
# methods will either be delete or annotated and moved to common.

import logging
# import lxml.etree

logger = logging.getLogger(__name__)

try:
    import autosocks

    autosocks.try_autosocks()
except ImportError:
    pass
