import asyncio
import logging

from src.spotycli.application.services import PlayerApplicationService, PlayerDataService
from src.spotycli.config import settings
from src.spotycli.infrastructure.mongo_adapter import MongoAdapter
from src.spotycli.infrastructure.spotify_adapter import SpotifyAdapter
from src.spotycli.logging_config import setup_logging
from src.spotycli.presentation.cli import CliController, SpotifyUI

setup_logging()
logger = logging.getLogger("main")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialize adapters
    mongo_adapter = MongoAdapter(settings)
    spotify_adapter = SpotifyAdapter(settings)

    # Initialize services
    player_data_service = PlayerDataService(mongo_adapter, spotify_adapter)
    player_app_service = PlayerApplicationService(spotify_adapter, player_data_service)

    # Initialize presentation layer
    cli_controller = CliController(player_app_service)
    ui = SpotifyUI(loop, cli_controller)

    asyncio.ensure_future(cli_controller.update_state_loop(ui.update_ui))
    ui.run()


if __name__ == "__main__":
    main()
