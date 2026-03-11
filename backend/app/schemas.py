"""Pydantic response models for API documentation and validation."""

from __future__ import annotations

from pydantic import BaseModel


class AudioFeaturesResponse(BaseModel):
    danceability: float | None = None
    energy: float | None = None
    valence: float | None = None
    acousticness: float | None = None
    instrumentalness: float | None = None
    liveness: float | None = None
    speechiness: float | None = None
    tempo: float | None = None


class TrackResponse(BaseModel):
    id: str
    name: str
    artist: str
    artist_id: str | None = None
    album: str = ""
    album_image: str | None = None
    popularity: int = 0
    duration_ms: int = 0
    preview_url: str | None = None
    features: AudioFeaturesResponse | None = None


class TopTracksResponse(BaseModel):
    tracks: list[TrackResponse]
    total: int
    time_range: str


class RecentTrackResponse(BaseModel):
    id: str | None = None
    name: str | None = None
    artist: str = "Sconosciuto"
    album: str = ""
    album_image: str | None = None
    played_at: str | None = None


class RecentTracksResponse(BaseModel):
    tracks: list[RecentTrackResponse]


class SavedTrackResponse(BaseModel):
    id: str
    name: str | None = None
    artist: str = "Sconosciuto"
    artist_id: str | None = None
    album: str = ""
    album_image: str | None = None
    popularity: int = 0
    added_at: str | None = None


class SavedTracksResponse(BaseModel):
    tracks: list[SavedTrackResponse]
    total: int
    offset: int


class PlaylistResponse(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    image: str | None = None
    track_count: int = 0
    owner: str = ""


class PlaylistListResponse(BaseModel):
    playlists: list[PlaylistResponse]
    total: int


class PlaylistComparisonTopTrack(BaseModel):
    name: str
    artist: str
    popularity: int


class PlaylistComparisonItem(BaseModel):
    playlist_id: str
    playlist_name: str = ""
    track_count: int
    analyzed_count: int = 0
    averages: dict[str, float] = {}
    popularity_stats: dict[str, float] = {}
    genre_distribution: dict[str, float] = {}
    top_tracks: list[PlaylistComparisonTopTrack] = []


class PlaylistComparisonResponse(BaseModel):
    comparisons: list[PlaylistComparisonItem]
