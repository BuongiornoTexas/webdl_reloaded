#!/usr/bin/env python3
"""Provides utility functions and classes for WebDL."""

# cspell:ignore webdl
# I've removed the following original webdl methods, as they were not being called
# anywhere. Recoverable from the original webdl archive.
#   def ensure_scheme(url):
#   def grab_html(url):
#   def check_command_exists(cmd):
#   def download_hds(filename, video_url, pvswf=None):
#   def download_mpd(filename, video_url):
#   def download_http(filename, video_url):

import io
import os
import re
import logging
import signal
import subprocess
import sys
import urllib.parse
import lxml.etree
import requests
import requests_cache


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0"

# TODO create logger for common

try:
    import autosocks

    autosocks.try_autosocks()
except ImportError:
    pass


logging.basicConfig(
    # Reverted to default python log format.
    # format="%(levelname)s %(message)s",
    level=logging.INFO if os.environ.get("DEBUG", None) is None else logging.DEBUG,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

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


def grab_xml(url):
    logger.debug("grab_xml(%r)", url)
    request = http_session.prepare_request(requests.Request("GET", url))
    response = http_session.send(request)
    doc = lxml.etree.parse(
        io.BytesIO(response.content),
        lxml.etree.XMLParser(encoding="utf-8", recover=True),
    )
    response.close()
    return doc


def grab_json(url):
    logger.debug("grab_json(%r)", url)
    request = http_session.prepare_request(requests.Request("GET", url))
    response = http_session.send(request)
    return response.json()


def exec_subprocess(cmd):
    logger.debug("Executing: %s", cmd)
    try:
        p = subprocess.Popen(cmd)
        ret = p.wait()
        if ret != 0:
            logger.error("%s exited with error code: %s", cmd[0], ret)
            return False
        else:
            return True
    except OSError as e:
        logger.error("Failed to run: %s -- %s", cmd[0], e)
    except KeyboardInterrupt:
        logger.info("Cancelled: %s", cmd)
        try:
            p.terminate()
            p.wait()
        except KeyboardInterrupt:
            p.send_signal(signal.SIGKILL)
            p.wait()
    return False


def get_duration(filename):
    cmd = [
        "ffprobe",
        filename,
        "-show_entries",
        "format=duration",
        "-v",
        "quiet",
    ]
    output = subprocess.check_output(cmd).decode("utf-8")
    for line in output.split("\n"):
        m = re.search(R"([0-9]+)", line)
        if not m:
            continue
        duration = m.group(1)
        if duration.isdigit():
            return int(duration)

    logger.debug("Falling back to full decode to find duration: %s % filename")

    cmd = [
        "ffmpeg",
        "-i",
        filename,
        "-vn",
        "-f",
        "null",
        "-",
    ]
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
    duration = None
    for line in re.split(R"[\r\n]", output):
        m = re.search(R"time=([0-9:]*)\.", line)
        if not m:
            continue
        [h, m, s] = m.group(1).split(":")
        # ffmpeg prints the duration as it reads the file, we want the last one
        duration = int(h) * 3600 + int(m) * 60 + int(s)

    if duration:
        return duration
    else:
        raise Exception("Unable to determine video duration of " + filename)


def check_video_durations(flv_filename, mp4_filename):
    flv_duration = get_duration(flv_filename)
    mp4_duration = get_duration(mp4_filename)

    if abs(flv_duration - mp4_duration) > 1:
        logger.error(
            "The duration of %s is suspicious, did the remux fail? Expected %s == %s",
            mp4_filename,
            flv_duration,
            mp4_duration,
        )
        return False

    return True


def remux(infile, outfile):
    # I've disabled processing to mp4. One day I might submit a PR as a long
    # term command line fix.
    print("remux has been disabled - use handbrake")
    return True

    logger.info("Converting %s to mp4", infile)

    cmd = [
        "ffmpeg",
        "-i",
        infile,
        "-bsf:a",
        "aac_adtstoasc",
        "-acodec",
        "copy",
        "-vcodec",
        "copy",
        "-y",
        outfile,
    ]
    if not exec_subprocess(cmd):
        return False

    if not check_video_durations(infile, outfile):
        return False

    os.unlink(infile)
    return True


def convert_to_mp4(filename) -> bool:
    """Convert file to .mp4 format."""
    with open(filename, "rb") as f:
        fourcc = f.read(4)
    basename, ext = os.path.splitext(filename)

    if ext == ".mp4" and fourcc == b"FLV\x01":
        os.rename(filename, basename + ".flv")
        ext = ".flv"
        filename = basename + ext

    if ext in (".flv", ".ts"):
        filename_mp4 = basename + ".mp4"
        return remux(filename, filename_mp4)

    return ext == ".mp4"


def download_hls(filename, video_url):
    filename = sanify_filename(filename)
    video_url = "hlsvariant://" + video_url
    logger.info("Downloading: %s", filename)

    cmd = [
        "streamlink",
        "--http-header",
        "User-Agent=" + USER_AGENT,
        "--force",
        "--output",
        filename,
        video_url,
        "best",
    ]
    if exec_subprocess(cmd):
        return convert_to_mp4(filename)
    else:
        return False


def natural_sort(l, key=None):
    ignore_list = ["a", "the"]

    def key_func(k):
        if key is not None:
            k = key(k)
        k = k.lower()
        newk = []
        for c in re.split("([0-9]+)", k):
            c = c.strip()
            if c.isdigit():
                newk.append(c.zfill(5))
            else:
                for subc in c.split():
                    if subc not in ignore_list:
                        newk.append(subc)
        return newk

    return sorted(l, key=key_func)


def append_to_qs(url, params):
    r = list(urllib.parse.urlsplit(url))
    qs = urllib.parse.parse_qs(r[3])
    for k, v in params.items():
        if v is not None:
            qs[k] = v
        elif k in qs:
            del qs[k]
    r[3] = urllib.parse.urlencode(sorted(qs.items()), True)
    url = urllib.parse.urlunsplit(r)
    return url
