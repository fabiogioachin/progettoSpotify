from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8001/auth/spotify/callback"

    session_secret: str = "cambiami-genera-con-openssl-rand-hex-32"
    frontend_url: str = "http://127.0.0.1:5173"
    backend_url: str = "http://127.0.0.1:8001"

    database_url: str = "sqlite+aiosqlite:///./data/spotify_intelligence.db"

    # Supabase (opzionale — se configurato, sovrascrive database_url)
    supabase_url: str = ""       # URL del progetto (es. https://xxxx.supabase.co)
    supabase_anon_key: str = ""  # Anon key per future integrazioni client-side
    supabase_db_url: str = ""    # Connection string PostgreSQL completa dal dashboard Supabase

    # Set to True in production (HTTPS)
    cookie_secure: bool = False

    # Generate a unique value per deployment for extra security
    encryption_salt: str = "spotify-intelligence-salt"

    # Token encryption key (derived from session_secret + encryption_salt)
    @property
    def encryption_key(self) -> bytes:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import base64

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.encryption_salt.encode(),
            iterations=480_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.session_secret.encode()))

    @property
    def effective_database_url(self) -> str:
        """Restituisce la URL del database effettiva.

        Se SUPABASE_DB_URL è configurato, converte la URL PostgreSQL standard
        nel formato asyncpg per SQLAlchemy. Altrimenti usa SQLite.
        """
        if self.supabase_db_url:
            url = self.supabase_db_url
            # Converti da postgresql:// a postgresql+asyncpg://
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        return self.database_url

    @property
    def is_using_supabase(self) -> bool:
        return bool(self.supabase_db_url)

    model_config = {"env_file": ".env", "extra": "ignore"}

    def validate_secrets(self):
        """Avvisa se i segreti di default sono in uso."""
        import logging
        log = logging.getLogger(__name__)
        if self.session_secret == "cambiami-genera-con-openssl-rand-hex-32":
            log.warning(
                "SECURITY: session_secret usa il valore di default! "
                "Genera un segreto con: openssl rand -hex 32"
            )
        if self.encryption_salt == "spotify-intelligence-salt":
            log.warning(
                "SECURITY: encryption_salt usa il valore di default! "
                "Imposta un salt unico per il deployment."
            )


settings = Settings()
settings.validate_secrets()
