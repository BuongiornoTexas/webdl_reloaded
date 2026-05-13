<!---
cspell:ignore Autograbber webdl delx pypi pydantic pyinstaller
--->

# TODO

- While ABC iView works, I recommend not using it until I have updated it to the new
naming convention.
- Ten is utterly broken at the moment. The fix will come after code cleanup on iView.

# WebDL Reloaded

This is a fork of the [webdl](https://bitbucket.org/delx/webdl/src/master/) project 
developed by delx. The original description of this project is:

    "WebDL is a set of Python scripts to grab video from online Free To Air Australian
    channels."

This fork updates the library to a relatively current version of python and replaces
many/all of the media download methods with calls to yt-dlp (yt-dlp is very much doing
the heavy lifting!). 

My reason for doing this fork is that I really like WebDL's ability to keep track of
historical downloads and the ability to set up fire and forget pattern based batch files
for checking streaming sites and grabbing new seasons of series. The move to yt-dlp is
based on the reasoning that it is the most actively developed downloader, so it just
makes sense to use it, especially as any updates to downloaders within WebDL would
likely just end up re-implementing yt-dlp code anyway (I'd prefer to cut out the
middleman).

This leads to an updated project description:

    "WebDL Reloaded is a wrapper for yt-dlp with a consistent user interface for
    accessing Australian FTA services. You can use this interactively or to download
    any shows matching a glob from a batch or cron job."

Much like everyone in this space, I love my Australian Free to Air services and
particularly their streaming offerings. And I really want them to remain easily
available for everyone. So whatever your other reasons for using this
package, please do not use it for piracy.

# Installation

If you are on windows, get the zip file from the
[releases page](https://www.github.com/BuongiornoTexas/webdl_reloaded/releases),
unzip and you are good to go. 

If you are using python on other systems, set up a virtual environment and install with
`pip install webdl_reloaded`.

Depending on your install, you can run the downloader using `webdl.exe` or
`py -m webdl_reloaded.webdl`.

## yt-dlp

You will also need `yt-dlp`, which you can grab from the
[releases page](https://github.com/yt-dlp/yt-dlp/releases). It's also worth checking the
[issues](https://github.com/yt-dlp/yt-dlp/issues) page and the relevant Whirlpool
threads (e.g. [SBS](https://forums.whirlpool.net.au/thread/3q6p5669?p=-1#bottom)) for
problems and workaround with `yt-dlp` and the Australian FTA providers (these can take
a while to resolve).

# Configuration

# Command Line Arguments

Webdl supports a limited set of command line options (most of the options are handled by
the configuration files detailed below).

- `-h`, `--help` Show this help message and exit
- `--config-dir CONFIG_DIR` Specify the configuration directory containing `webdl.toml`.
Refer to the documentation for default file locations if this option is not used.
Creates a partial template if the file does not exist.
- `--target-dir TARGET_DIR` Override the destination directory(ies) specified in 
`webdl.toml`. Note: `webdl.toml` still controls local use of yt-dlp.
- `--interactive` Run webdl in interactive (grabber) mode on the **first** valid target
directory it finds. Without this flag, WebDL defaults to batch (autograbber) mode.
- `--simulate` Simulated run. Logs/prints information about file downloads, but does not
call yt-dlp.

## webdl.toml

When run, the downloader will look for `webdl.toml` in the following locations (priority
order):

- The configuration location specified by the command line argument `--config-dir`. 
- If a command line location is not specified:
    - The current working directory.
    - If you are using a pyinstaller executable, the same location as the executable.

(If you want to use the same location as the executable, you need to create or move the
config file to this location.)

If the `webdl.toml` file is not found, `webdl` will create a partial template as
follows:
- If you specified `--config-dir` command line argument, it will be created in that 
location.
- Otherwise the file will be created in the current working directory.

A typical `webdl.toml` is:

```
allow_target_yt_dlp = false
allow_target_yt_dlp_conf = false
yt_dlp_location = "D:/Users/buongiornotexas/Documents/Programs/webdlexe"
target_dirs = [
    "D:/Users/buongiornotexas/Documents/Programs/sbs", 
    "D:/Users/buongiornotexas/Documents/Programs/abc"
]
```

- `yt_dlp_location` is the path to the default yt-dlp executable.
- `target_dirs` is a list of target directories to process in batch mode. Interactive
mode will download to the first valid target it finds and exit (and so you should
probably use the `--target-dir` command line argument when in interactive mode). This
list assumes a separate folder for SBS and ABC, but you can do it all in one directory,
or by show, or by movie, etc.
- If `allow_target_yt_dlp` is`true`, `webdl` will look for and prefer to use a `yt-dlp`
executable in each target directory.
- If `allow_target_yt_dlp_conf` is`true`, `webdl` will look for and prefer to use a
`yt-dlp.conf` configuration file in each target directory.

## `yt-dlp.conf`

`webdl` will look for a `yt-dlp.conf` file:
- In each target directory if enabled with `allow_target_yt_dlp_conf`.
- In the same directory as `webdl.toml` if not found in the target directories.

`webdl` will run without a `yt-dlp.conf` file, but even if you don't want to use it, 
I'd recommend setting up an empty default file as standard (right at the moment, 
it's mandatory for SBS authentication anyway).

Aside from the requirement to use the name `yt-dlp.conf` and the locations specified
above, everything else about this file follows the rules detailed in the yt-dlp 
[README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md#configuration)
including:
- The ability to reference other config files.
- Set the preferred behaviour of yt-dlp.

Note that `webdl` uses `--paths` to send output to the target directory and `--output`
to specify an output filename pattern of `<webdl title>.%(ext)`, where `<webdl title>`
follows the webdl internal naming convention. I suspect both of these could be
overridden, but I haven't tried yet.

My testing yt-dlp.conf file looks like:

```
# .netrc location
--netrc 
--netrc-location 'D:/Users/buongiornotexas/Documents/Programs/webdlexe/.netrc'

--write-all-thumbnails
--write-description
--sub-lang "en"
--convert-subs srt
--write-sub
```
Importantly, right at the moment SBS requires authentication for download, which is
currently supplied by a .netrc file of the format:

```
machine sbs
login <email@address.com>
password <sbspassword>
```
If you don't want to use .netrc, you'll need to follow up on one of the alternatives in
the yt-dlp docs.

## Everything with the Executable

As discussed in the previous section, there are several ways to setup and run
`webdl`. For my setup, I have a functional folder that looks like this:
    ![Functional folder](./images/Functional%20folder.png)

`webdl.toml` points to the local yt-dlp executable and contains the list of my preferred
download folders.

I then run webdl from a cmd shell opened in the functional folder with any of the
following:

```
# Interactive testing:
c:> webdl --interactive --simulate
# Interactive mode
C:> webdl --interactive
# Batch testing:
c:> webdl --simulate
# Batch downloads
C:> webdl 
```

# Interactive Usage

Interactive mode is driven by a simple text menu:

```
webdl.exe --interactive
<snipped>
   1) ABC iView
   2) SBS
   3) Ten
   0) Back
Choose> 2
   1) Movies
   2) News
   3) Sports
   4) TV Shows
   0) Back
Choose> 3
INFO:webdl_reloaded.nodes_sbs:Fetching 'browse-all-sport' catalogue.
INFO:webdl_reloaded.nodes_sbs:  Expect '238' item.
INFO:webdl_reloaded.nodes_sbs:  Fetched 238 items.
   1) All
   2) Athletics
   3) Court Sports
   4) Cycling
<snipped>
Choose> 4
   1) AlUla Tour 2024
   2) AlUla Tour 2025
   3) Amstel Gold 2025: Men's Race
Choose> 3
   1) Amstel Gold 2025: Men's Race  S2025E01 Full Race (SBS)
   2) Amstel Gold 2025: Men's Race  S2025E02 Highlights (SBS)
   3) Amstel Gold 2025: Men's Race  S2025E03 Winning Moment (SBS)
   0) Back
Choose> 1-2
[SBS] Extracting URL: https://www.sbs.com.au/ondemand/watch/2417911363987
<Snipped>
```
Note 1: When you get to a downloadable node, you can select a single download with a
single number, or multiple sequential downloads using `<n1-n2>` or a list of space
separated numbers `<n1 n2 n3>`. But if you want multiple downloads, you are likely
better off using pattern files and batch mode.

Note 2: See the commentary about
[Single Shows as Episodes](#single-shows-as-episodes) below.

# Batch Mode Usage

Batch mode is designed to run as scheduled task/batch job. For windows, you can run
these using the task scheduler (TODO: Add section on task scheduler), and for Linux you
can run a cron job - I'm unfamiliar with cron, so I refer you to the section on cron
usage in the
[original WebDL README](Original%20webdl%20README.md#cron-scripted-usage-autograbberpy).

Batch mode also runs happily in a terminal, and it's a good place to start when testing
patterns. I'd also suggest running in simulate mode when doing your trials so you can 
see what would be downloaded. 

For batch mode, each target directory should contain a `.patterns.txt` with shell-style
globs (wildcards). These follow the same structure as the interactive menu system
detailed in the previous section (#'s are comments and shouldn't be included in your
`.patterns.txt`):

```
# Pull down the Cycling shows demoed in the previous section.
SBS/Sports/Cycling/Amstel*Men*/*
# Or using the All category.
SBS/Sports/Cycling/Amstel*Men*/*
# Pull down all seasons of Bosch.
SBS/TV Shows/All/Bosch/*
# Or
SBS/TV Shows/Drama/Bosch/*
# Season 3 of Bosch
SBS/TV Shows/Drama/Bosch/*S3E*
# Season 3 Episode 1 of Bosch
SBS/TV Shows/Drama/Bosch/*S3E01*
# Recent NSW news broadcasts
ABC iView/By Category/News*/ABC News NSW/*
```

Whenever an episode is downloaded it is recorded into `.history.txt`. Even if you move
the files somewhere else they will not be redownloaded.

To make things a bit easier to find shows where genres are all over the place (Hi SBS),
I'm trying to incorporate an "All" bucket category which gathers everything in a
subcategory. This makes some patterns a bit easier and more robust to re-categorisation
in the future. E.g. The Americans is currently classed as Thriller
(SBS/TV Shows/Thriller), but could easily move to the general Drama (SBS/TV Shows/Drama)
category in the future. To avoid this, try using (SBS/TV Shows/All/The Americans). 
Definitely available for SBS at the moment, hopefully coming to ABC and Ten soon.


**This next bit is untested** at the moment. You may optionally created a 
`.excludes.txt` file with shell-style globs. This is matched against the episode title
and can be used to filter out things you don't want. For example:

```
*(Mandarin)*
*(Chinese)*
```

## Single Shows as Episodes

Single shows (non-series type things like movies, specials, etc.) may have an
implementation oddity where you select the media container by name, and the media item
with the same name in the container - this happens when `webdl` treats these single
show events as a series with one episode. For example, in interactive mode:

```
   1) 100 Yards
   2) The Assassin
   3) The Big Boss
   4) Big Brother
   5) The Bodyguard From Beijing
Choose> 2
   1) The Assassin (SBS)
   0) Back
```

The correct way to handle this pattern is `.../The Assassin/*` (mildly annoying, but
so much easier for me to code).

# Changes from OG WebDL

- There is now a single entry point to grabber and autograbber (webdl.py or webdl.exe).

## Autograbber

- **Major change:** Name formats for TV series in the `.history.txt` file are being
  moved to a consistent pattern of:

      <series name> S<series number>E<Episode number> <episode title> (Provider)
      
  For example "Bosch S1E05 Mama's Boy (SBS)". 

  This is complete for SBS, pending for ABC and Ten (I'd suggest not using this
  package for those providers until the updates are done).
  
  The script`fix_history.py` provides a starting point for converting an old
  school history file, but it will still  require a bit of manual intervention/cleanup
  to do a full conversion (the --simulate flag is very useful here). If you are facing
  problems with this conversion, please raise an
  [issue](https://github.com/BuongiornoTexas/webdl_reloaded/issues). 
- Pattern files are no longer supported as command line arguments.
- Each directory specified as an autograbber target must contain a pattern file named
`.patterns.txt`. If you have a (very) old `patterns.txt` file, you can rename it to
fix the problem.
- The structure of patterns has changed! Most patterns will need updating.
- The extremely old history files `downloaded_auto.txt` and `.downloaded_auto.txt` are 
no longer fixed automatically. If you still have one of these a) I'm impressed with how
long you have kept your home rolled setup running! and b) renaming the file to 
`.history.txt` will fix the file name problem (you will probably still need to update
the history entries).
- The original webdl command line arguments are no longer supported. Refer to the
configuration section for updated command line arguments.

(Yeah, there have been a few changes!)

# Roadmap

- ~~Convert to a src based library~~ and commit to pypi.
- Add annotations - in progress.
- Follow the SBS model of using pydantic to convert API json into python objects.
  - Pending for both 10play and ABC.
- Get 10Play back online.
- Add logging to make batch and interactive mode more talky (no long pauses with nothing
happening).
- Lint all files properly after cleanup.
