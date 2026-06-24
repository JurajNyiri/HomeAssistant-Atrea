from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.util import slugify

from .const import DOMAIN


class AtreaEntityBase:
    def init_atrea_entity(self, hass, entry, name_suffix, unique_suffix):
        self.data = hass.data[DOMAIN][entry.entry_id]
        self.atrea = self.data["atrea"]
        self.ip = entry.data.get(CONF_IP_ADDRESS)
        self._name_suffix = name_suffix
        self._unique_suffix = unique_suffix
        self._id = self.atrea.getID()
        self._model = self.data["model"]
        self._swVersion = self.atrea.getVersion()

    def getUniqueID(self):
        return slugify(f"atrea_{self.ip}_{self._unique_suffix}")

    def getDeviceUniqueID(self):
        return slugify(f"atrea_{self.ip}")

    @property
    def brand(self):
        return "ATREA s.r.o."

    @property
    def model(self):
        if self._model:
            return self._model["category"] + " " + self._model["model"]
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.getDeviceUniqueID())},
            "name": self.data.get("name", "Atrea"),
            "manufacturer": self.brand,
            "model": self.model,
            "sw_version": self._swVersion,
            "hw_version": self._id,
            "connections": {},
        }

    @property
    def unique_id(self) -> str:
        return self.getUniqueID()

    @property
    def name(self):
        return f"{self.data.get('name', 'Atrea')} {self._name_suffix}"
