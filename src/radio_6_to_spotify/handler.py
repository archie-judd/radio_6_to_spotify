import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from radio_6_to_spotify.internal_types import Playlist, Track
from radio_6_to_spotify.scrape import scrape_radio_6_playlist_tracks
from radio_6_to_spotify.spotify import Spotify

logger = logging.getLogger(__name__)


class Environment(BaseModel):
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REFRESH_TOKEN: str
    SPOTIFY_RADIO_6_SYNCHED_PLAYLIST_ID: str
    SPOTIFY_RADIO_6_ARCHIVE_PLAYLIST_ID: str


ENVIRONMENT = Environment.model_validate(os.environ)
SPECIAL_CHARACTERS_PATTEN = r"[^ \w+-.]"


def make_updated_playlist_description(description: str) -> str:
    ts = datetime.now(tz=ZoneInfo("Europe/London")).strftime("%d-%m-%Y %H:%M:%S (%Z)")
    description_without_date = "Last updated: ".join(
        description.split("Last updated: ")[0:-1]
    )
    new_description = f"{description_without_date} Last updated: {ts}"

    return new_description


def has_special_characters(string: str) -> bool:
    res = re.search(pattern=SPECIAL_CHARACTERS_PATTEN, string=string)
    has = bool(res)
    return has


def remove_special_characters(string: str) -> str:
    string = re.sub(pattern=SPECIAL_CHARACTERS_PATTEN, repl="", string=string)
    return string


def get_playlist(spotify_client: Spotify, playlist_id: str) -> Playlist:
    playlist_model = spotify_client.get_playlist(playlist_id=playlist_id)
    playlist = Playlist.from_external(playlist_model)
    return playlist


def get_tracks_by_artist_and_track_name(
    spotify_client: Spotify,
    artist: str,
    track_name: str,
    retry_without_special_characters: bool = True,
) -> set[Track]:
    track_models = spotify_client.search_for_track_by_artist_and_track_name(
        artist=artist, track_name=track_name
    )
    if not track_models and (
        retry_without_special_characters
        and (has_special_characters(artist) or has_special_characters(track_name))
    ):
        artist_ = remove_special_characters(artist)
        track_name_ = remove_special_characters(track_name)
        track_models = spotify_client.search_for_track_by_artist_and_track_name(
            artist=artist_, track_name=track_name_
        )
    tracks = {Track.from_external(track_model) for track_model in track_models}
    return tracks


def scrape_current_tracks_and_get_from_spotify(
    spotify_client: Spotify,
) -> set[Track]:
    scraped_current_tracks = scrape_radio_6_playlist_tracks()
    current_tracks: set[Track] = set()
    for scraped_track in scraped_current_tracks:
        spotify_tracks = get_tracks_by_artist_and_track_name(
            spotify_client=spotify_client,
            artist=scraped_track.artist,
            track_name=scraped_track.name,
        )
        if spotify_tracks:
            tracks = sorted(
                list(spotify_tracks),
                key=lambda x: (x.popularity, x.id),
                reverse=True,  # make deterministic
            )
            current_tracks.add(tracks[0])

    return current_tracks


def update_playlist_with_current_tracks(
    spotify_client: Spotify,
    playlist_id: str,
    current_tracks: set[Track],
    remove_outdated_tracks: bool,
):
    playlist = get_playlist(spotify_client=spotify_client, playlist_id=playlist_id)

    existing_tracks = set(playlist.tracks)
    tracks_to_add = current_tracks.difference(existing_tracks)
    uris_to_add = [track.uri for track in tracks_to_add]

    if uris_to_add:
        logger.info(
            "Addings these tracks: %s to playlist: %s",
            [track.name for track in tracks_to_add],
            playlist_id,
        )
        spotify_client.add_to_playlist(playlist_id=playlist.id, track_uris=uris_to_add)

    if remove_outdated_tracks:
        tracks_to_remove = existing_tracks.difference(current_tracks)
        uris_to_remove = [track.uri for track in tracks_to_remove]
        if uris_to_remove:
            logger.info(
                "Removing these tracks: %s to playlist: %s",
                [track.name for track in tracks_to_remove],
                playlist_id,
            )
            spotify_client.remove_from_playlist(
                playlist_id=playlist.id, track_uris=uris_to_remove
            )

    updated_description = make_updated_playlist_description(playlist.description)
    spotify_client.change_playlist_details(
        playlist_id=playlist_id,
        description=updated_description,
    )


def handler():

    logger.info("Starting")

    spotify_client = Spotify(
        client_id=ENVIRONMENT.SPOTIFY_CLIENT_ID,
        client_secret=ENVIRONMENT.SPOTIFY_CLIENT_SECRET,
        refresh_token=ENVIRONMENT.SPOTIFY_REFRESH_TOKEN,
    )

    current_tracks = scrape_current_tracks_and_get_from_spotify(
        spotify_client=spotify_client
    )

    update_playlist_with_current_tracks(
        spotify_client=spotify_client,
        playlist_id=ENVIRONMENT.SPOTIFY_RADIO_6_SYNCHED_PLAYLIST_ID,
        current_tracks=current_tracks,
        remove_outdated_tracks=True,
    )
    update_playlist_with_current_tracks(
        spotify_client=spotify_client,
        playlist_id=ENVIRONMENT.SPOTIFY_RADIO_6_ARCHIVE_PLAYLIST_ID,
        current_tracks=current_tracks,
        remove_outdated_tracks=False,
    )

    logger.info("Done")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S %Z",
    )
    handler()
