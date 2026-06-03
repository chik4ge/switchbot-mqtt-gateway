import asyncio
import logging

from switchbot_mqtt_gateway import __version__
from switchbot_mqtt_gateway.gateway import Gateway
from switchbot_mqtt_gateway.settings import Settings
from switchbot_mqtt_gateway.utils import log


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(message)s")
    log("gateway_starting", version=__version__)
    asyncio.run(Gateway(settings).run())


if __name__ == "__main__":
    main()
