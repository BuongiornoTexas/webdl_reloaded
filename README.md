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

# Roadmap

- Update code with minor hacks I've incorporated to keep the original code running.
- Implement a temporary SBS fix. 
- Convert to a src based library and commit to pypi.
- Add annotations.
- Convert downloader method calls to external yt-dlp calls.
- Get 10Play back online.
