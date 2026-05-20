#!/usr/bin/env python3
# cspell:ignore MEIPASS, dotenv autograbber
"""Provides utility functions and classes for WebDL."""

# cspell:ignore webdl
# I've removed the following original webdl methods, as they were not being called
# anywhere. Recoverable from the original webdl archive.
#   def ensure_scheme(url):
#   def grab_html(url):
#   def check_command_exists(cmd):
#   def download_hds(filename, video_url, =None):
#   def download_mpd(filename, video_url):
#   def download_http(filename, video_url):


import re
import os
import logging
import sys

from argparse import ArgumentParser
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple, Callable

# TODO - figure out what auto-socks is doing and un-monkey patch if possible.
# Importing to get side effect of setting up auto-socks.
import webdl_reloaded.old_common
import requests
import requests_cache
import urllib.parse

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)
from tomli_w import dump as dump_toml

# Per https://github.com/pydantic/pydantic-settings/issues/259, use a global
# hack to allow cli config file location.
CONFIG_DIR: Path | None = None
CONFIG_FILE = "webdl.toml"
if sys.platform == "win32":
    YT_DLP_FILE = "yt-dlp.exe"
else:
    # I think this should be good for macos, linux
    YT_DLP_FILE = "yt-dlp"

YT_DLP_CONFIG_FILE = "yt-dlp.conf"

logging.basicConfig(
    # Reverted to default python log format.
    # format="%(levelname)s %(message)s",
    level=logging.INFO if os.environ.get("DEBUG", None) is None else logging.DEBUG,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Setup requests.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0"
CACHE_PATH = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "webdl"
if not CACHE_PATH.exists():
    CACHE_PATH.mkdir()

requests_cache.install_cache(
    CACHE_PATH / "requests_cache", backend="sqlite", expire_after=3600
)
# Global session for requests.
http_session = requests.Session()
http_session.headers["User-Agent"] = USER_AGENT


def grab_text(url: str) -> str:
    """GET url text response."""
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


def grab_json(url: str) -> Any:
    """GET url response as JSON."""
    logger.debug("grab_json(%r)", url)
    request = http_session.prepare_request(requests.Request("GET", url))
    response = http_session.send(request)
    return response.json()


class WebDLPaths(NamedTuple):
    """Provide paths for target folder and yt-dlp execution."""

    target_dir_path: Path
    yt_dlp_path: Path
    yt_dlp_conf_path: Path | None


valid_chars = frozenset(
    "-_.()!@#%^ abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)


def sanitize_filename(filename: str) -> str:
    """Remove unsafe characters from filename."""
    # Not used currently.
    filename = "".join(c for c in filename if c in valid_chars)
    assert len(filename) > 0
    return filename


def natural_sort(list_to_sort: list[Any], key: Callable | None = None) -> list[Any]:
    """Perform natural sort on list."""
    # TODO figure out what this code is actually doing!
    ignore_list = ["a", "the"]

    def key_func(k: str) -> list[str]:
        """Provide natural sort key function."""
        if key is not None:
            k = key(k)
        k = k.lower()
        new_k = []
        for c in re.split("([0-9]+)", k):
            c = c.strip()
            if c.isdigit():
                new_k.append(c.zfill(5))
            else:
                for sub_c in c.split():
                    if sub_c not in ignore_list:
                        new_k.append(sub_c)
        return new_k

    return sorted(list_to_sort, key=key_func)


def append_to_query_string(url: str, params: dict[str, str]) -> str:
    """Add parameters to url query string."""
    r = list(urllib.parse.urlsplit(url))
    qs = urllib.parse.parse_qs(r[3])
    for k, v in params.items():
        if v is not None:
            qs[k] = [v]
        elif k in qs:
            del qs[k]
    r[3] = urllib.parse.urlencode(sorted(qs.items()), True)
    url = urllib.parse.urlunsplit(r)
    return url


class Settings(BaseSettings):
    """Rough and ready settings via pydantic."""

    allow_target_yt_dlp: bool = False
    allow_target_yt_dlp_conf: bool = False
    yt_dlp_location: str = ""
    # Not implemented yet
    target_dirs: list[str] = []
    _config_file: Path | None = None
    # Simulate and interactive should not be stored. So use property methods.
    _simulate: bool = False
    _interactive: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customise settings to use toml file only."""
        global CONFIG_DIR  # pylint: disable=W0603

        if CONFIG_DIR:
            CONFIG_DIR = CONFIG_DIR.resolve()
            # Capture invalid command line arg
            if not CONFIG_DIR.is_dir():
                raise NotADirectoryError(
                    f"Configuration location {CONFIG_DIR} must exist and"
                    f" must be a directory"
                )
        else:
            # CONFIG_DIR is None, so check for config file in default
            # locations. If we don't find the config file, we make
            # CONFIG_DIR the current directory and post_init will generate
            # the default file.
            # For use by pydantic settings DON'T raiser errors here!
            CONFIG_DIR = Path.cwd()
            if not (CONFIG_DIR / CONFIG_FILE).is_file():
                # Not found, so check if we are using a windows binary and
                # if the file exists in the same folder as the binary.
                # Find the location of the binary source file per pyinstaller docs for
                # one folder app.
                if getattr(sys, "frozen", False):
                    # we are running in a bundle
                    # sys._MEIPASS returns pyinstaller _internal folder.
                    # For a bundle, we will put the file in the parent folder with
                    # the bundle exe.
                    config_path = Path(
                        # pylint: disable-next=protected-access
                        sys._MEIPASS  # type: ignore[attr-defined]
                    ).parent
                    if (config_path / CONFIG_FILE).is_file():
                        # Found the config file! Update config dir.
                        CONFIG_DIR = config_path

        # Only toml settings allowed.
        # Config file is not guaranteed to exist, in which case defaults apply
        # at instantiation.
        config_path = CONFIG_DIR / CONFIG_FILE
        return (TomlConfigSettingsSource(settings_cls, toml_file=config_path),)

    def model_post_init(self, context: Any, /) -> None:
        """Fix unsafe settings and resave.

        pydantic does the basic validation, but path/file validity is only checked in
        self.webdl_paths. This is because I haven't properly integrated the cli and
        the toml read (pydantic supports it, but more effort than it's worth today),
        and so Settings doesn't get a full set of parameters until initialised from
        argparse - so I push this validation from initialisation to first use.
        """
        # Finalise the config file location.
        assert CONFIG_DIR is not None
        self._config_file = CONFIG_DIR / CONFIG_FILE
        if not self._config_file.exists():
            self.save()
            logger.error(
                "'%s' not found. Templated created (needs editing).", CONFIG_FILE
            )
            logger.error("Template file: '%s'", self._config_file)
            raise FileNotFoundError(f"'{CONFIG_FILE}' not found, template created.")

    @property
    def simulate(self) -> bool:
        """Return simulate."""
        return self._simulate

    @simulate.setter
    def simulate(self, value: bool) -> None:
        """Set simulate."""
        self._simulate = value

    @property
    def interactive(self) -> bool:
        """Return interactive."""
        return self._interactive

    @interactive.setter
    def interactive(self, value: bool) -> None:
        """Set interactive."""
        self._interactive = value

    def save(self) -> None:
        """Write settings to the default location."""
        # Assertion should never be triggered.
        assert self._config_file is not None
        with open(self._config_file, "wb") as fp:
            dump_toml(self.model_dump(), fp)

    @staticmethod
    def _check_path(location: str | Path, file_name: str = "") -> Path | None:
        """Check if location or location/file exists and returns path to item or None.

        Empty string for location returns None.
        """
        if not location:
            return None

        if isinstance(location, Path):
            check = location.resolve()
        else:
            check = Path(location).resolve()

        if not file_name:
            if check.is_dir():
                return check
            return None

        check = check / file_name
        if check.is_file():
            return check

        return None

    def webdl_paths(self) -> Iterator[WebDLPaths]:
        """Provide WebDl path information for each target directory in settings."""
        if len(self.target_dirs) == 0:
            logger.error("No target directories specified.")
            logger.error(
                "Either update 'webdl.toml' or provide an override with --target_dir."
            )
            # Let's make this terminal. Not much caller can do if there are no
            # targets.
            raise FileNotFoundError("No target directories specified.")

        # Construct and check paths.
        for target in self.target_dirs:
            target_path = self._check_path(target)
            if not target_path:
                logger.error(
                    "Target path '%s' is not a directory. Target skipped.", target
                )
                continue
            logger.info("Target directory set to '%s'", target_path)

            yt_dlp_path = None
            if self.allow_target_yt_dlp:
                yt_dlp_path = self._check_path(target, YT_DLP_FILE)
            if yt_dlp_path is None:
                yt_dlp_path = self._check_path(self.yt_dlp_location, YT_DLP_FILE)
            if yt_dlp_path is None:
                logger.error(
                    "Target directory '%s' skipped. yt-dlp executable not found.",
                    target_path,
                )
                continue
            logger.info("yt-dlp path set to '%s'", yt_dlp_path)

            yt_dlp_conf_path = None
            if self.allow_target_yt_dlp_conf:
                yt_dlp_conf_path = self._check_path(target, YT_DLP_CONFIG_FILE)
            if yt_dlp_conf_path is None:
                assert self._config_file is not None
                yt_dlp_conf_path = self._check_path(
                    self._config_file.parent, YT_DLP_CONFIG_FILE
                )
            if yt_dlp_conf_path is None:
                logger.info(
                    "yt-dlp config '%s' not found for target path '%s'.",
                    YT_DLP_CONFIG_FILE,
                    target_path,
                )
                logger.info("yt-dlp will run without config.")
            else:
                logger.info("yt-dlp conf path set to '%s'", yt_dlp_conf_path)

            assert target_path is not None
            yield WebDLPaths(
                target_dir_path=target_path,
                yt_dlp_path=yt_dlp_path,
                yt_dlp_conf_path=yt_dlp_conf_path,
            )


def process_args() -> Settings:
    """Process shared grabber/autograbber command line."""
    parser = ArgumentParser(
        description="A downloader for Australian FTA streaming services."
    )

    parser.add_argument(
        "--config-dir",
        metavar="CONFIG_DIR",
        help=(
            "Specify the configuration directory containing 'webdl.toml'. Refer to the"
            " documentation for default file locations if this option is not used."
            " Creates a partial template if the file does not exist."
        ),
    )

    parser.add_argument(
        "--target-dir",
        metavar="TARGET_DIR",
        help=(
            "Override the destination directory(ies) specified in 'webdl.toml'."
            " Note: 'webdl.toml' still controls local use of yt-dlp."
        ),
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help=(
            "Run webdl in interactive (grabber) mode on the **first** valid target"
            " directory it finds. Without this flag, WebDL defaults to batch"
            " (autograbber) mode."
        ),
    )

    parser.add_argument(
        "--simulate",
        action="store_true",
        help=(
            "Simulated run. Logs/prints information about file downloads, but does"
            " not call yt-dlp."
        ),
    )
    args = parser.parse_args()

    # Fix up CONFIG_DIR before instantiating Settings.
    if args.config_dir:
        # pylint: disable-next=global-statement
        global CONFIG_DIR
        CONFIG_DIR = Path(args.config_dir).resolve()

    settings = Settings()

    # Update settings with args. I really need to sort out doing this via pydantic.
    settings.simulate = args.simulate
    settings.interactive = args.interactive

    if args.target_dir:
        if not Path(args.target_dir).resolve().is_dir():
            raise NotADirectoryError(
                f"Target '{args.target_dir}' is not a directory')."
            )
        settings.target_dirs = [args.target_dir]

    return settings
