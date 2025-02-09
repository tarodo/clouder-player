from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    env: str = "dev"
    log_level: str = "INFO"
    mongo_url: str
    mongo_db: str
    spotipy_client_id: str
    spotipy_client_secret: str
    spotipy_redirect_uri: str

    class Config:
        env_file = ".env"


settings = AppSettings()
