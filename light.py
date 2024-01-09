from homeassistant.components.light import LightEntity, ATTR_RGB_COLOR, ATTR_BRIGHTNESS
from . import DOMAIN
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up World Map Entity Manager light entities."""
    coordinator = hass.data[DOMAIN]['coordinator']
    api_url = hass.data[DOMAIN]['API_URL']
    session = hass.data[DOMAIN]['session']

    if not coordinator.data:
        _LOGGER.info("No data received for entities. Skipping entity setup.")
        return

    entities = [EntityManagerLightEntity(entity_data, coordinator, api_url, session) for entity_data in coordinator.data]
    async_add_entities(entities, True)

class EntityManagerLightEntity(LightEntity):
    """Representation of an Entity from the external system."""

    def __init__(self, entity_data, coordinator, api_url, session):
        """Initialize the entity."""
        self._entity_data = entity_data
        self.coordinator = coordinator
        self.api_url = api_url
        self._attr_unique_id = entity_data["id"]
        self._attr_name = entity_data["name"]
        self.session = session

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._entity_data["state"]["is_on"]

    async def async_turn_on(self, **kwargs):
        """Turn on the light through the external API."""
        turn_on_data = {
            "entity": self._attr_unique_id,
            "is_on": False
        }

        try:
            async with self.session.post(f"{self.api_url}/toggle/", json=turn_on_data) as response:
                _LOGGER.error(f"Response: {response}")
                _LOGGER.error(f"Response status: {response.status}")
                _LOGGER.error(f"Response text: {await response.text()}")
                _LOGGER.error(f"Response json: {await response.json()}")
                if response.status == 200:
                    response_data = await response.json()  # Correctly await the result
                    if response_data["is_on"] == turn_on_data["is_on"]:
                        self._entity_data["state"]["is_on"] = True
                        _LOGGER.info(f"Turned on entity {self._attr_unique_id}")
                    else:
                        self._entity_data["state"]["is_on"] = response_data["is_on"]
                        _LOGGER.error(f"Failed to turn on entity: {response_data}")
                else:
                    error_message = await response.text()
                    _LOGGER.error(f"Failed to turn on entity: {error_message}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error communicating with API to turn on entity: {e}")

    async def async_turn_off(self, **kwargs):
        """Turn off the light through the external API."""
        turn_off_data = {
            "entity": self._attr_unique_id,
            "is_on": False
        }

        try:
            async with self.session.post(f"{self.api_url}/toggle/", json=turn_off_data) as response:
                _LOGGER.error(f"Response: {response}")
                _LOGGER.error(f"Response status: {response.status}")
                _LOGGER.error(f"Response text: {await response.text()}")
                _LOGGER.error(f"Response json: {await response.json()}")
                if response.status == 200:
                    response_data = await response.json()  # Correctly await the result
                    if response_data["is_on"] == turn_off_data["is_on"]:
                        self._entity_data["state"]["is_on"] = False
                        _LOGGER.info(f"Turned off entity {self._attr_unique_id}")
                    else:
                        self._entity_data["state"]["is_on"] = response_data["is_on"]
                        _LOGGER.error(f"Failed to turn off entity: {response_data}")
                else:
                    error_message = await response.text()
                    _LOGGER.error(f"Failed to turn off entity: {error_message}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error communicating with API to turn off entity: {e}")

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Handle additional setup when entity is added to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._entity_data["state"]["brightness"]
    
    @property
    def rgb_color(self):
        """Return the rgb color of the light."""
        return self._entity_data["state"]["rgb_color"]