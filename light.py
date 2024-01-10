from homeassistant.components.light import LightEntity, ATTR_RGB_COLOR, ATTR_BRIGHTNESS
from homeassistant.components.light import SUPPORT_BRIGHTNESS, SUPPORT_COLOR
from homeassistant.util.color import color_hs_to_RGB
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
    def brightness(self):
        """Return the brightness of the light."""
        return self._entity_data["state"]["brightness"]
    
    @property
    def rgb_color(self):
        """Return the rgb color of the light."""
        return self._entity_data["state"].get("rgb_color", (255, 255, 255))

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR
    
    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._entity_data["state"]["is_on"]

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        data = {"entity": self._attr_unique_id, "is_on": True}

        # Check if color or brightness is specified in kwargs and update data accordingly
        if ATTR_RGB_COLOR in kwargs or ATTR_BRIGHTNESS in kwargs:
            color_brightness_data = self._prepare_color_data(kwargs)
            data.update(color_brightness_data)
        else:
            # Use existing color data if no color or brightness is specified
            color_data = self._prepare_color_data(kwargs)
            data.update(color_data)

        await self._send_color_request(data)

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        data = {"entity": self._attr_unique_id, "is_on": False}
        await self._send_color_request(data)

    async def async_set_color(self, **kwargs):
        """Set the color and brightness of the light."""
        data = {"entity": self._attr_unique_id, "is_on": True}

        if ATTR_RGB_COLOR in kwargs or ATTR_BRIGHTNESS in kwargs:
            color_brightness_data = self._prepare_color_data(kwargs)
            data.update(color_brightness_data)
        else:
            # Use existing color data if no color or brightness is specified
            color_data = self._prepare_color_data(kwargs)
            data.update(color_data)

        await self._send_color_request(data)

    def _prepare_color_data(self, kwargs):
        """Prepare the current color and brightness data based on kwargs or current state."""
        log = []
        log.append(f"Prepare Color Data for entity {self._attr_unique_id}")
        log.append(f"Initial kwargs: {kwargs}")

        # Check if HS color is provided, then convert to RGB
        if 'hs_color' in kwargs:
            hs_color = kwargs['hs_color']
            rgb_color = color_hs_to_RGB(*hs_color)
        else:
            rgb_color = self.rgb_color or (0, 0, 0)

        log.append(f"RGB Color: {rgb_color}")
        log.append(f"Red: {rgb_color[0]}")
        log.append(f"Green: {rgb_color[1]}")
        log.append(f"Blue: {rgb_color[2]}")

        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 0)

        log.append(f"Brightness: {brightness}")

        _LOGGER.error(log)

        return {
            "red": rgb_color[0],
            "green": rgb_color[1],
            "blue": rgb_color[2],
            "brightness": 100 #int(brightness / 255 * 100)
        }

    def _update_entity_data(self, data):
        """Update the internal state of the entity."""
        if "is_on" in data:
            self._entity_data["state"]["is_on"] = data["is_on"]
        if "red" in data and "green" in data and "blue" in data:
            self._entity_data["state"]["rgb_color"] = (data["red"], data["green"], data["blue"])
        if "brightness" in data:
            # Scale up brightness to 0-255 range
            self._entity_data["state"]["brightness"] = int(data["brightness"] / 100 * 255)

    async def _send_color_request(self, data):
        socketio_client = self.hass.data[DOMAIN]['websocket']
        if socketio_client:
            try:
                # Emit the message to the Flask-SocketIO server
                await socketio_client.emit('set_color', data, namespace='/ws-color')
                _LOGGER.info(f"Sent color update via WebSocket for entity {self._attr_unique_id}")
            except Exception as e:
                _LOGGER.error(f"Error sending message via WebSocket: {e}, falling back to REST API")
                await self._send_color_request_fallback(data)
        else:
            _LOGGER.error(f"No WebSocket connection available, falling back to REST API")
            await self._send_color_request_fallback(data)

    async def _send_color_request_fallback(self, data):
        try:
            async with self.session.post(f"{self.api_url}/color/", json=data) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data.get("success"):
                        self._update_entity_data_from_response(response_data)
                        _LOGGER.info(f"Updated color for entity {self._attr_unique_id}")
                    else:
                        _LOGGER.error(f"API response indicates failure: {response_data}")
                else:
                    error_message = await response.text()
                    _LOGGER.error(f"Failed to set color for entity: {error_message}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error communicating with API to set color: {e}")

    def _update_entity_data_from_response(self, data):
        """Update the internal state of the entity from API response."""
        self._entity_data["state"]["is_on"] = data.get("is_on", self.is_on)
        self._entity_data["state"]["rgb_color"] = (data.get("red", 0), data.get("green", 0), data.get("blue", 0))
        self._entity_data["state"]["brightness"] = int(data.get("brightness", 0) / 100 * 255)

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Handle additional setup when entity is added to Home Assistant."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

