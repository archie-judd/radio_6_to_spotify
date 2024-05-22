from dataclasses import dataclass
from typing import Self

from radio_6_to_spotify.spotify import (
    AlbumModel,
    ArtistModel,
    PlaylistModel,
    TrackModel,
)


@dataclass(frozen=True)
class Artist:
    name: str
    uri: str
    id: str

    @classmethod
    def from_external(cls, artist_model: ArtistModel) -> Self:
        artist = cls(name=artist_model.name, uri=artist_model.uri, id=artist_model.id)
        return artist

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True)
class Album:
    name: str
    artists: list[Artist]
    uri: str
    id: str

    @classmethod
    def from_external(cls, album_model: AlbumModel) -> Self:
        artists = [
            Artist.from_external(artist_model) for artist_model in album_model.artists
        ]
        album = cls(
            name=album_model.name,
            artists=artists,
            uri=album_model.uri,
            id=album_model.id,
        )
        return album

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True)
class Track:
    album: Album
    artists: list[Artist]
    name: str
    uri: str
    id: str
    popularity: int

    @classmethod
    def from_external(cls, track_model: TrackModel) -> Self:
        album = Album.from_external(track_model.album)
        artists = [
            Artist.from_external(artist_model) for artist_model in track_model.artists
        ]
        track = cls(
            album=album,
            artists=artists,
            name=track_model.name,
            uri=track_model.uri,
            id=track_model.id,
            popularity=track_model.popularity,
        )
        return track

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class Playlist:
    tracks: list[Track]
    collaborative: bool
    description: str
    name: str
    public: bool
    uri: str
    id: str

    @classmethod
    def from_external(cls, playlist_model: PlaylistModel) -> Self:

        tracks = [
            Track.from_external(track_with_meta_model.track)
            for track_with_meta_model in playlist_model.tracks.items
        ]

        playlist = cls(
            tracks=tracks,
            collaborative=playlist_model.collaborative,
            description=playlist_model.description,
            name=playlist_model.name,
            public=playlist_model.public,
            uri=playlist_model.uri,
            id=playlist_model.id,
        )

        return playlist

    def __hash__(self) -> int:
        return hash(self.id)
