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
# TODO fix this for macos, linux
YT_DLP_FILE = "yt-dlp.exe"
YT_DLP_CONFIG_FILE = "yt-dlp.conf"

logging.basicConfig(
    # Reverted to default python log format.
    # format="%(levelname)s %(message)s",
    level=logging.INFO if os.environ.get("DEBUG", None) is None else logging.DEBUG,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


class WebDLPaths(NamedTuple):
    """Provide paths for target folder and yt-dlp execution."""

    target_dir_path: Path
    yt_dlp_path: Path
    yt_dlp_conf_path: Path | None


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
            err_str = (
                f"`{CONFIG_FILE}` not found. Templated created (needs editing):"
                f"\n  `{self._config_file}`"
            )
            logger.error(err_str)
            raise FileNotFoundError(err_str)

    def save(self) -> None:
        """Write settings to the default location."""
        # Assertion should never be triggered.
        assert self._config_file is not None
        with open(self._config_file, "wb") as fp:
            dump_toml(self.model_dump(), fp)

    @staticmethod
    def _check_file_path(path: str | Path, file_name: str) -> Path | None:
        """Check if file exists and returns path to file."""
        if isinstance(path, Path):
            check = path
        else:
            check = Path(path)

        check = check.resolve() / file_name
        if check.is_file():
            return check

        return None

    def webdl_paths(self) -> Iterator[WebDLPaths]:
        """Provide WebDl path information for each target directory in settings."""
        if len(self.target_dirs) == 0:
            err_str = (
                "No target directories specified. Either update 'webdl.toml'"
                " or provide an override with --target_dir."
            )
            logger.error(err_str)
            # Let's make this terminal. Not much caller can do if there are no
            # targets.
            raise FileNotFoundError(err_str)

        # Construct and check paths.
        for target in self.target_dirs:
            target_path = Path(target).resolve()
            if not target_path.is_dir():
                logger.error(
                    "Target path '%s' is not a directory. Target skipped.", target_path
                )
                continue

            yt_dlp_path = None
            if self.allow_target_yt_dlp:
                yt_dlp_path = self._check_file_path(target, YT_DLP_FILE)
            if yt_dlp_path is None:
                yt_dlp_path = self._check_file_path(self.yt_dlp_location, YT_DLP_FILE)
            if yt_dlp_path is None:
                logger.error(
                    (
                        "yt-dlp executable not found for target path '%s'."
                        "\n  Target directory skipped."
                        "\n  Either yt_dlp_location must be specified in 'webdl.toml'"
                        "\n  or 'allow_target_yt_dlp' must be 'true' and yt-dlp must"
                        "\n  exist in target directory."
                    ),
                    target_path,
                )
                continue

            yt_dlp_conf_path = None
            if self.allow_target_yt_dlp_conf:
                yt_dlp_conf_path = self._check_file_path(target, YT_DLP_CONFIG_FILE)
            if yt_dlp_conf_path is None:
                assert self._config_file is not None
                yt_dlp_conf_path = self._check_file_path(
                    self._config_file.parent, YT_DLP_CONFIG_FILE
                )
            if yt_dlp_conf_path is None:
                logger.info(
                    (
                        "yt-dlp config '%s' not found for target path '%s'."
                        "\n  yt_dlp will run without config. To use a config file"
                        "\n  either 'yt_dlp.conf' must exist in the same directory as"
                        "\n  'webdl.toml', or 'allow_target_yt_dlp_conf' must be 'true'"
                        "\n  and 'yt-dlp.conf' must exist in target directory."
                    ),
                    YT_DLP_CONFIG_FILE,
                    target_path,
                )

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
        ),
    )

    parser.add_argument(
        "--target-dir",
        metavar="TARGET_DIR",
        help=(
            "Override the destination directory(ies) specified in 'webdl.toml'."
            "\n  Note: 'webdl.toml' still controls local use of yt-dlp."
        ),
    )

    args = parser.parse_args()

    # Fix up CONFIG_DIR
    if args.config_dir:
        # pylint: disable-next=global-statement
        global CONFIG_DIR
        CONFIG_DIR = Path(args.config_dir).resolve()

    settings = Settings()

    if args.target_dir:
        if not Path(args.target_dir).resolve().is_dir():
            raise NotADirectoryError(
                f"Target '{args.target_dir}' is not a directory')."
            )
        settings.target_dirs = [args.target_dir]

    return settings
