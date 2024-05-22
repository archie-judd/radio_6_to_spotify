import logging
import time
from typing import Literal, Optional
from urllib.parse import urljoin

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


SCOPE = "playlist-modify-public playlist-modify-private"


class SearchParams(BaseModel):
    q: str
    type: str
    market: str | None = None
    limit: int


class AddItemsToPlaylistParams(BaseModel):
    uris: str


class GetAuthenticationCodeParams(BaseModel):
    client_id: str
    redirect_uri: str
    scope: str
    response_type: Literal["code"] = "code"


class GetRefreshTokenBody(BaseModel):
    code: str
    client_id: str
    client_secret: str
    redirect_uri: str
    grant_type: Literal["authorization_code"] = "authorization_code"


class GetAccessTokenBody(BaseModel):
    refresh_token: str
    client_id: str
    client_secret: str
    grant_type: Literal["refresh_token"] = "refresh_token"


class TrackURI(BaseModel):
    uri: str


class RemovePlaylistItemsBody(BaseModel):
    tracks: list[TrackURI]


class ChangePlaylistDetailsBody(BaseModel):
    name: str | None = None
    public: bool | None = None
    collaborative: bool | None = None
    description: str | None = None


class ArtistModel(BaseModel):
    name: str
    uri: str
    id: str


class AlbumModel(BaseModel):
    name: str
    artists: list[ArtistModel]
    uri: str
    id: str


class TrackModel(BaseModel):
    album: AlbumModel
    artists: list[ArtistModel]
    name: str
    uri: str
    id: str
    popularity: int


class TrackWithMetaModel(BaseModel):
    track: TrackModel


class TracksWithMetaModel(BaseModel):
    items: list[TrackWithMetaModel]


class TracksModel(BaseModel):
    items: list[TrackModel]


class PlaylistMetaModel(BaseModel):
    collaborative: bool
    description: str
    name: str
    public: bool
    uri: str
    id: str


class PlaylistModel(PlaylistMetaModel):
    tracks: TracksWithMetaModel
    collaborative: bool
    description: str
    name: str
    public: bool
    uri: str
    id: str


class GetPlaylistsResponse(BaseModel):
    items: list[PlaylistMetaModel]


class GetPlaylistResponse(PlaylistModel):
    tracks: TracksWithMetaModel


class TrackSearchResponse(BaseModel):
    tracks: TracksModel


def check_access_token(func):
    def wrapper(*args, **kwargs):
        spotify = args[0]
        if spotify.token_ts is None:
            logger.debug("No access token. Getting one")
            spotify.get_new_access_token()
        elif time.time() > spotify.token_ts + spotify.access_token_timeout - 300:
            logger.debug("Refreshing access token")
            spotify.get_new_access_token()
        else:
            logger.debug("Access token in date")

        res = func(*args, **kwargs)

        return res

    return wrapper


class Spotify:
    base_url = "https://api.spotify.com"
    accounts_base_url = "https://accounts.spotify.com"
    version = "v1"
    access_token_timeout = 3600

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        access_token: Optional[str] = None,
        access_token_ts: Optional[float] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

        self.access_token = access_token
        self.token_ts = access_token_ts

    def api_call(
        self,
        url: str,
        method: Literal["get", "put", "post", "delete"] = "get",
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        headers: Optional[dict] = None,
        json: Optional[dict] = None,
        timeout_s: int = 30,
    ) -> requests.Response:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout_s,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise requests.HTTPError(response.json()) from exc
        return response

    @property
    def authorization_headers(self) -> dict:
        headers = {"Authorization": "Bearer {}".format(self.access_token)}
        return headers

    @classmethod
    def get_authorization_code(
        cls, client_id: str, scope: str, redirect_uri: str = "http://localhost/"
    ) -> None:
        url_ext = "authorize"
        url = urljoin(base=cls.accounts_base_url, url=url_ext)

        params = GetAuthenticationCodeParams(
            client_id=client_id, redirect_uri=redirect_uri, scope=scope
        )

        response = requests.get(url=url, params=params, timeout=30)
        print(
            f"Paste this URL into your browser.....\n{response.url}\nYou will be"
            " redirected to a URL with the authentication code in it."
        )

    @classmethod
    def get_refresh_token(
        cls,
        authentication_code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost/",
    ):
        url_ext = "api/token"
        url = urljoin(base=cls.accounts_base_url, url=url_ext)
        body = GetRefreshTokenBody(
            code=authentication_code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        ).model_dump()

        response = requests.post(url=url, data=body, timeout=30)
        print(response.json())
        print("ts:\n{}".format(time.time()))

    def get_new_access_token(self):
        logger.debug("Getting new access_token")
        url_ext = "/api/token"
        url = urljoin(base=self.accounts_base_url, url=url_ext)
        body = GetAccessTokenBody(
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
        ).model_dump()

        response = self.api_call(
            url=url,
            method="post",
            data=body,
        )
        content = response.json()
        self.access_token = content["access_token"]
        self.token_ts = time.time()

    @check_access_token
    def search(
        self,
        query: str,
        thing_type: str,
        market: Optional[str] = None,
        limit: int = 20,
    ):
        url_ext = f"{self.version}/search"
        url = urljoin(base=self.base_url, url=url_ext)

        params = SearchParams(
            q=query, type=thing_type, market=market, limit=limit
        ).model_dump(exclude_none=True)

        response = self.api_call(
            url=url,
            method="get",
            headers=self.authorization_headers,
            params=params,
        )

        return response.json()

    @check_access_token
    def get_track(self, track_id: str, market: Optional[str] = None) -> TrackModel:
        url_ext = f"{self.version}/tracks/{track_id}"
        if market is not None:
            url_ext += f"?market={market}"
        url = urljoin(base=self.base_url, url=url_ext)

        response = self.api_call(
            url=url, method="get", headers=self.authorization_headers
        )

        track = TrackModel.model_validate(response.json())

        return track

    @check_access_token
    def get_user_playlists(self, user_id: str) -> list[PlaylistMetaModel]:
        url_ext = f"{self.version}/users/{user_id}/playlists"
        url = urljoin(base=self.base_url, url=url_ext)

        response = self.api_call(
            url=url, method="get", headers=self.authorization_headers
        )

        playlists = GetPlaylistsResponse.model_validate(response.json()).items

        return playlists

    @check_access_token
    def get_playlist(self, playlist_id: str) -> PlaylistModel:
        url_ext = f"{self.version}/playlists/{playlist_id}"
        url = urljoin(base=self.base_url, url=url_ext)

        response = self.api_call(
            url=url, method="get", headers=self.authorization_headers
        )

        playlist = PlaylistModel.model_validate(response.json())

        return playlist

    @check_access_token
    def add_to_playlist(self, playlist_id: str, track_uris: list[str]):
        url_ext = f"{self.version}/playlists/{playlist_id}/tracks"
        url = urljoin(base=self.base_url, url=url_ext)

        params = AddItemsToPlaylistParams(uris=",".join(track_uris)).model_dump()

        logger.debug("Adding: %s", params)

        self.api_call(
            url, method="post", headers=self.authorization_headers, params=params
        )

    @check_access_token
    def remove_from_playlist(self, playlist_id: str, track_uris: list[str]):
        url_ext = f"{self.version}/playlists/{playlist_id}/tracks"
        url = urljoin(base=self.base_url, url=url_ext)

        headers = self.authorization_headers
        headers.update({"Content-Type": "application/json"})

        tracks = [TrackURI(uri=uri) for uri in track_uris]

        data = RemovePlaylistItemsBody(tracks=tracks).model_dump()

        logger.debug("Removing : %s", data)

        self.api_call(
            url=url,
            method="delete",
            headers=headers,
            json=data,
        )

    @check_access_token
    def change_playlist_details(
        self,
        playlist_id: str,
        name: Optional[str] = None,
        public: Optional[bool] = None,
        collaborative: Optional[bool] = None,
        description: Optional[str] = None,
    ):
        url_ext = f"{self.version}/playlists/{playlist_id}"
        url = urljoin(base=self.base_url, url=url_ext)

        headers = self.authorization_headers
        headers.update({"Content-Type": "application/json"})

        data = ChangePlaylistDetailsBody(
            name=name,
            public=public,
            collaborative=collaborative,
            description=description,
        ).model_dump(exclude_none=True)

        self.api_call(url, method="put", headers=self.authorization_headers, json=data)

    @check_access_token
    def search_for_track_by_artist_and_track_name(
        self, artist: str, track_name: str, market: Optional[str] = None
    ) -> list[TrackModel]:
        query = f"artist:{artist} track:{track_name}"
        result = self.search(
            query=query,
            thing_type="track",
            market=market,
        )

        track_search_response = TrackSearchResponse.model_validate(result)

        tracks = track_search_response.tracks.items

        return tracks
