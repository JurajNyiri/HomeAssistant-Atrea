from pyatrea import Atrea
from .const import LOGGER


def isAtreaUnit(host):
    atrea = Atrea(host, "")
    return atrea.isAtreaUnit()


async def update_listener(hass, entry):
    LOGGER.warn("update_listener")
