import logging
import os
import re
from datetime import datetime
from typing import Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from radio_6_to_spotify.radio_6_music import (
    ScrapedTrack,
    scrape_radio_6_playlist_tracks,
)
from radio_6_to_spotify.spotify import Spotify, Track

logger = logging.getLogger(__name__)


class Environment(BaseModel):
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REFRESH_TOKEN: str
    SPOTIFY_RADIO_6_PLAYLIST_ID: str


ENVIRONMENT = Environment.model_validate(os.environ)


def get_updated_playlist_description(description: str) -> str:
    ts = datetime.now(tz=ZoneInfo("Europe/London")).strftime("%d-%m-%Y %H:%M:%S (%Z)")

    description_without_date = "Last updated: ".join(
        description.split("Last updated: ")[0:-1]
    )
    new_description = f"{description_without_date} Last updated: {ts}"

    return new_description


def has_odd_chars(string: str) -> bool:
    res = re.search(pattern=r"[^ \w+-.]", string=string)
    has = bool(res)
    return has


def remove_odd_chars(string: str) -> str:
    string = re.sub(pattern=r"[^ \w+-.]", repl="", string=string)
    return string


def get_scraped_track_alphanumeric(scraped_track: ScrapedTrack, spotify: Spotify):

    artist_alphanumeric = remove_odd_chars(scraped_track.artist)
    track_name_alphanumeric = remove_odd_chars(scraped_track.track)

    tracks = spotify.search_for_track_by_artist_and_track_name(
        artist=artist_alphanumeric, track_name=track_name_alphanumeric
    )

    if tracks:
        logger.info(
            """Found track for artist '%s' and track_name '%s' with special characters
            removed.""",
            scraped_track.artist,
            scraped_track.track,
        )

    return tracks


def get_track_from_spotify(
    scraped_track: ScrapedTrack, spotify: Spotify
) -> Union[Track, None]:
    tracks = spotify.search_for_track_by_artist_and_track_name(
        artist=scraped_track.artist, track_name=scraped_track.track
    )

    if not tracks and (
        has_odd_chars(scraped_track.artist) or has_odd_chars(scraped_track.track)
    ):

        logger.warning(
            (
                "Could not find track for artist '%s' and track_name '%s'. Trying"
                " without special characters."
            ),
            scraped_track.artist,
            scraped_track.track,
        )

        tracks = get_scraped_track_alphanumeric(
            scraped_track=scraped_track, spotify=spotify
        )

    if tracks:
        logger.debug("Found track: %s", scraped_track)
        tracks = sorted(tracks, key=lambda x: x.popularity, reverse=True)
        track = tracks[0]
    else:
        logger.warning("Could not find: %s", scraped_track)
        track = None

    return track


def get_scraped_tracks_from_spotify(
    scraped_tracks: list[ScrapedTrack], spotify: Spotify
) -> list[Track]:
    tracks: list[Track] = []

    for scraped_track in scraped_tracks:
        track = get_track_from_spotify(scraped_track=scraped_track, spotify=spotify)

        if track is not None:
            tracks.append(track)

    return tracks


def is_track_in_tracks(track: Track, tracks: list[Track]) -> bool:

    match = False
    for track_to_check in tracks:
        id_match = track.id == track_to_check.id
        name_and_artist_match = (track.name == track_to_check.name) and (
            track.artists == track_to_check.artists
        )
        if id_match or name_and_artist_match:
            match = True
            break

    return match


def get_tracks_to_add_and_remove_from_playlist(
    spotify_tracks: list[Track], scraped_tracks: list[Track]
) -> tuple[list[Track], list[Track]]:
    tracks_to_remove: list[Track] = []
    tracks_to_add: list[Track] = []

    for track in spotify_tracks:
        if not is_track_in_tracks(track=track, tracks=scraped_tracks):
            tracks_to_remove.append(track)

    for track in scraped_tracks:
        if not is_track_in_tracks(track=track, tracks=spotify_tracks):
            tracks_to_add.append(track)

    return tracks_to_add, tracks_to_remove


def handler():
    spotify = Spotify(
        client_id=ENVIRONMENT.SPOTIFY_CLIENT_ID,
        client_secret=ENVIRONMENT.SPOTIFY_CLIENT_SECRET,
        refresh_token=ENVIRONMENT.SPOTIFY_REFRESH_TOKEN,
    )
    spotify_playlist = spotify.get_playlist(
        playlist_id=ENVIRONMENT.SPOTIFY_RADIO_6_PLAYLIST_ID
    )
    spotify_tracks = [
        track_with_meta.track for track_with_meta in spotify_playlist.tracks.items
    ]

    scraped_tracks = scrape_radio_6_playlist_tracks()
    scraped_tracks = get_scraped_tracks_from_spotify(
        scraped_tracks=scraped_tracks, spotify=spotify
    )
    tracks_to_add, tracks_to_remove = get_tracks_to_add_and_remove_from_playlist(
        spotify_tracks=spotify_tracks, scraped_tracks=scraped_tracks
    )

    if tracks_to_add:
        logger.info("Addings these tracks: %s", [track.name for track in tracks_to_add])
        uris_to_add = [track.uri for track in tracks_to_add]
        spotify.add_to_playlist(
            playlist_id=ENVIRONMENT.SPOTIFY_RADIO_6_PLAYLIST_ID, track_uris=uris_to_add
        )
    if tracks_to_remove:
        logger.info(
            "Removing these tracks: %s", [track.name for track in tracks_to_remove]
        )
        uris_to_remove = [track.uri for track in tracks_to_remove]
        spotify.remove_from_playlist(
            playlist_id=ENVIRONMENT.SPOTIFY_RADIO_6_PLAYLIST_ID,
            track_uris=uris_to_remove,
        )

    updated_description = get_updated_playlist_description(spotify_playlist.description)
    spotify.change_playlist_details(
        playlist_id=ENVIRONMENT.SPOTIFY_RADIO_6_PLAYLIST_ID,
        description=updated_description,
    )

    logger.info(
        "Added %s tracks. Removed %s tracks.", len(tracks_to_add), len(tracks_to_remove)
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S %Z",
    )
    handler()
