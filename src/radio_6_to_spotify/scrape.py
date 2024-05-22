import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup as bs
from bs4.element import NavigableString, Tag

logger = logging.getLogger(__name__)


@dataclass
class ScrapedTrack:
    name: str
    artist: str


RADIO_6_MUSIC_PLAYLIST_URL = """https://www.bbc.co.uk/programmes/articles/5JDPyPdDGs3yCLdtPhGgWM7/bbc-radio-6-music-playlist"""


def scrape_primary_artist(artist: str) -> str:
    artist_primary = artist.replace("&", "ft.").split("ft.")[0]
    return artist_primary


def scrape_all_navigable_strings_from_tag(tag: Tag) -> list[NavigableString]:
    strings = []
    for child in tag.children:
        if isinstance(child, Tag):
            child_strings = scrape_all_navigable_strings_from_tag(tag=child)
            strings.extend(child_strings)
        elif isinstance(child, NavigableString):
            strings.append(child)
    return strings


def scrape_songs_from_para(para: Tag) -> list[ScrapedTrack]:
    scraped_tracks: list[ScrapedTrack] = []
    navigable_strings = scrape_all_navigable_strings_from_tag(tag=para)
    for navigable_string in navigable_strings:
        artist = navigable_string.text.split(" - ")[0]
        primary_artist = scrape_primary_artist(artist)
        track_name = navigable_string.text.split(" - ")[-1]
        scraped_tracks.append(ScrapedTrack(artist=primary_artist, name=track_name))
    return scraped_tracks


def scrape_tracks_in_section(section: Tag) -> list[ScrapedTrack]:
    scraped_tracks = []
    paras = section.find_all("p")
    for para in paras:
        para_tracks = scrape_songs_from_para(para=para)
        scraped_tracks.extend(para_tracks)
    return scraped_tracks


def scrape_radio_6_playlist_tracks() -> list[ScrapedTrack]:
    scraped_tracks: list[ScrapedTrack] = []

    page = requests.get(url=RADIO_6_MUSIC_PLAYLIST_URL, timeout=30)
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
            section_tracks = scrape_tracks_in_section(section=section)
            scraped_tracks.extend(section_tracks)

    logger.debug("Scraped %s tracks.\n%s", len(scraped_tracks), scraped_tracks)

    return scraped_tracks
