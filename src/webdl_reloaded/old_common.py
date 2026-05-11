#!/usr/bin/env python3
# Contains original webdl code still waiting on cleanup.
# methods will either be delete or annotated and moved to common.

# TODO Replace os.path with Pathlib
import os
# import io
import logging
import requests
import requests_cache
# import lxml.etree

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0"

logger = logging.getLogger(__name__)

try:
    import autosocks

    autosocks.try_autosocks()
except ImportError:
    pass

CACHE_FILE = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "webdl",
    "requests_cache",
)
if not os.path.isdir(os.path.dirname(CACHE_FILE)):
    os.makedirs(os.path.dirname(CACHE_FILE))

requests_cache.install_cache(CACHE_FILE, backend="sqlite", expire_after=3600)

valid_chars = frozenset(
    "-_.()!@#%^ abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)


def sanify_filename(filename):
    filename = "".join(c for c in filename if c in valid_chars)
    assert len(filename) > 0
    return filename


http_session = requests.Session()
http_session.headers["User-Agent"] = USER_AGENT


def grab_text(url):
    logger.debug("grab_text(%r)", url)
    request = http_session.prepare_request(requests.Request("GET", url))
    response = http_session.send(request)
    return response.text

# Disabling this for now, as xml isn't used anywhere in webdl at the moment.
# Can remove lxml from dependencies while this isn't needed.
# def grab_xml(url):
#    logger.debug("grab_xml(%r)", url)
#    request = http_session.prepare_request(requests.Request("GET", url))
#    response = http_session.send(request)
#    doc = lxml.etree.parse(
#        io.BytesIO(response.content),
#        lxml.etree.XMLParser(encoding="utf-8", recover=True),
#    )
#    response.close()
#    return doc


def grab_json(url):
    logger.debug("grab_json(%r)", url)
    request = http_session.prepare_request(requests.Request("GET", url))
    response = http_session.send(request)
    return response.json()
