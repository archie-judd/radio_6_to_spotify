import logging

import requests
from bs4 import BeautifulSoup as bs
from bs4.element import NavigableString, Tag
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ScrapedTrack(BaseModel):
    artist: str
    track: str


RADIO_6_MUSIC__PLAYLIST_URL = """https://www.bbc.co.uk/programmes/articles/
5JDPyPdDGs3yCLdtPhGgWM7/bbc-radio-6-music-playlist"""


def get_core_artist(artist: str) -> str:
    artist_core = artist.replace("&", "ft.").split("ft.")[0]
    return artist_core


def get_all_navigable_strings_from_tag(tag: Tag) -> list[NavigableString]:
    strings = []
    for child in tag.children:
        if isinstance(child, Tag):
            child_strings = get_all_navigable_strings_from_tag(tag=child)
            strings.extend(child_strings)
        elif isinstance(child, NavigableString):
            strings.append(child)
    return strings


def get_songs_from_para(para: Tag) -> list[ScrapedTrack]:
    tracks: list[ScrapedTrack] = []
    navigable_strings = get_all_navigable_strings_from_tag(tag=para)
    for navigable_string in navigable_strings:
        artist = navigable_string.text.split(" - ")[0]
        artist = get_core_artist(artist)
        track = navigable_string.text.split(" - ")[-1]
        tracks.append(ScrapedTrack(artist=artist, track=track))
    return tracks


def get_tracks_in_section(section: Tag) -> list[ScrapedTrack]:
    tracks = []
    paras = section.find_all("p")
    for para in paras:
        para_tracks = get_songs_from_para(para=para)
        tracks.extend(para_tracks)
    return tracks


def scrape_radio_6_playlist_tracks() -> list[ScrapedTrack]:
    tracks: list[ScrapedTrack] = []

    page = requests.get(url=RADIO_6_MUSIC__PLAYLIST_URL, timeout=30)
    soup = bs(markup=page.content, features="html.parser")

    sections = soup.find_all(
        class_=(
            "component component--box component--box-flushbody-vertical"
            " component--box--primary"
        )
    )
    for section in sections:
        headers: list[Tag] = section.find_all("h2")

        if not headers:
            continue
        header = headers[0].text.strip()

        if header.endswith("LIST"):
            section_tracks = get_tracks_in_section(section=section)
            tracks.extend(section_tracks)

    logger.debug("Scraped %s tracks.\n%s", len(tracks), tracks)

    return tracks
