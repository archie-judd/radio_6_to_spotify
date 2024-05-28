#!/usr/bin/env bash
cd /Users/Archie/repos/radio_6_to_spotify
source .envrc
$(poetry env info --path)/bin/python src/radio_6_to_spotify/handler.py 2>&1 | tee ./radio_6_to_spotify.log
