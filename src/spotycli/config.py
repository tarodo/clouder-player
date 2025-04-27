from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    env: str = "dev"
    log_level: str = "INFO"
    mongo_url: str
    mongo_db: str
    spotipy_client_id: str
    spotipy_client_secret: str
    spotipy_redirect_uri: str
    yt_client_id: str
    yt_client_secret: str
    perplexity_api_key: str
    anthropic_api_key: str

    class Config:
        env_file = ".env"


settings = AppSettings()
