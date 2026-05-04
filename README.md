<!---
cspell:ignore Autograbber webdl delx pypi pydantic
--->

# TODO

# WebDL Reloaded

This is a fork of the (webdl)[https://bitbucket.org/delx/webdl/src/master/] project 
developed by delx. The original description of this project is:

    "WebDL is a set of Python scripts to grab video from online Free To Air Australian
    channels."

This fork updates the library to a relatively current version of python and replaces
many/all of the media download methods with calls to yt-dlp. 

My reason for doing this fork is that I really like WebDL's ability to keep track of
historical downloads and the ability to set up fire and forget pattern based batch files
for checking streaming sites and grabbing new seasons of series. The move to yt-dlp is
based on the reasoning that it is the most actively developed downloader, so it just
makes sense to use it, especially as any updates to downloaders with WebDL will end up
largely re-implementing yt-dlp code anyway (I'd prefer to cut out the middleman).

# Upgrading from OG WebDL

## Autograbber

- Pattern files are no longer supported as command line arguments. 
- Each directory specified as an autograbber target must contain a pattern file named
`.patterns.txt`. If you have a (very) old `patterns.txt` file, you can rename it to
fix the problem.
- The extremely old history files `downloaded_auto.txt` and `.downloaded_auto.txt` are 
no longer fixed automatically. If you still have one of these a) I'm impressed with how
long you have kept your home rolled setup running! and b) renaming the file to 
`.history.txt` will fix the problem.

# Roadmap

- Update code with minor hacks I've incorporated to keep the original code running.
- Implement a temporary SBS fix. 
- Convert to a src based library and commit to pypi.
- Add annotations.
- Convert downloader method calls to external yt-dlp calls.
- Convert Node class to pydantic BaseModel. Should make loading json a lot simpler.
Pretty sure pydantic's inheritance is strong enough to make this relatively easy.
- Get 10Play back online.
- ~~Removed backwards compatibility with old autograbber argument format (pattern~~
~~file must now appear in each directory).~~


