from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class AudioFeatures(Base):
    __tablename__ = "audio_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    danceability = Column(Float)
    energy = Column(Float)
    valence = Column(Float)
    acousticness = Column(Float)
    instrumentalness = Column(Float)
    liveness = Column(Float)
    speechiness = Column(Float)
    tempo = Column(Float)
    loudness = Column(Float)
    key = Column(Integer)
    mode = Column(Integer)
    time_signature = Column(Integer)
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ArtistGenre(Base):
    """Cache persistente generi artista (TTL 7 giorni)."""

    __tablename__ = "artist_genres"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artist_spotify_id = Column(String(64), unique=True, nullable=False, index=True)
    artist_name = Column(String(500), nullable=True)
    genres = Column(Text, nullable=False, default="[]")  # JSON array of strings
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TrackMetadata(Base):
    """Copertina e album di un brano.

    La cronologia degli ascolti salva titolo, artista e orario, non l'immagine:
    senza questa tabella le classifiche costruite sugli ascolti resterebbero
    senza copertine. Non scade — la copertina di un album non cambia. La riga
    viene scritta anche quando l'immagine manca, cosi' non si richiede due volte.
    """

    __tablename__ = "track_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    album_name = Column(String(500), nullable=True)
    album_image = Column(String, nullable=True)
    preview_url = Column(String, nullable=True)
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TrackPopularity(Base):
    """Cache per popularity dei brani (enrichment centralizzato)."""

    __tablename__ = "track_popularity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    popularity = Column(Integer, nullable=False, default=0)
    cached_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GlobalChartEntry(Base):
    """La classifica mondiale, una riga per posizione.

    Non ha colonna utente per scelta: il dato e' identico per chiunque apra la
    pagina, e tenerne una copia per utente moltiplicherebbe le chiamate verso
    Last.fm senza aggiungere nulla. La tabella si riscrive per intero a ogni
    aggiornamento riuscito.
    """

    __tablename__ = "global_chart_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rank = Column(Integer, nullable=False, index=True)
    track_name = Column(String(500), nullable=False)
    artist_name = Column(String(500), nullable=False)
    playcount = Column(Integer, nullable=True)
    listeners = Column(Integer, nullable=True)
    image = Column(String, nullable=True)
    url = Column(String, nullable=True)
    source = Column(String(32), nullable=False, default="lastfm")
    fetched_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class TrackWorldPlaycount(Base):
    """Quante volte il mondo ha ascoltato un brano, secondo Last.fm.

    Prende il posto di `track_popularity`, che resta vuota perche' Spotify in
    dev mode non restituisce piu' il campo `popularity`. La chiave e' la coppia
    artista+titolo normalizzata, non l'id Spotify: Last.fm non conosce gli id
    di Spotify, e lo stesso brano puo' arrivare con id diversi da album diversi.
    """

    __tablename__ = "track_world_playcount"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lookup_key = Column(String(512), unique=True, nullable=False, index=True)
    artist_name = Column(String(500), nullable=False)
    track_name = Column(String(500), nullable=False)
    playcount = Column(Integer, nullable=True)
    cached_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
