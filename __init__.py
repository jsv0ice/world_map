import requests
import aiohttp
from homeassistant.core import HomeAssistant, ConfigEntry, ServiceCall
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import LightEntity
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import _LOGGER


DOMAIN = "entity_manager"
API_URL = "http://your-api-url"  # Replace with your actual API URL

# Define the schema for your service calls
CREATE_ENTITY_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("start_addr"): cv.positive_int,
    vol.Required("end_addr"): cv.positive_int,
    vol.Optional("parent_id"): cv.positive_int,
})

UPDATE_ENTITY_SCHEMA = vol.Schema({
    vol.Required("id"): cv.positive_int,
    vol.Required("name"): cv.string,
    vol.Required("start_addr"): cv.positive_int,
    vol.Required("end_addr"): cv.positive_int,
    vol.Optional("parent_id"): cv.positive_int,
})

DELETE_ENTITY_SCHEMA = vol.Schema({
    vol.Required("id"): cv.positive_int,
})

SET_COLOR_SCHEMA = vol.Schema({
    vol.Required("entity"): cv.positive_int,
    vol.Required("red"): cv.byte,
    vol.Required("green"): cv.byte,
    vol.Required("blue"): cv.byte,
    vol.Required("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Required("is_on"): cv.boolean,
})

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""

    # Create an aiohttp session for HTTP requests
    session = aiohttp.ClientSession()

    # Set up DataUpdateCoordinator
    coordinator = DataUpdateCoordinator(
        hass,
        name="entity_manager",
        update_method=lambda: async_update_data(session),
        update_interval=timedelta(minutes=1),
    )
    await coordinator.async_refresh()

    if coordinator.data is not None:
        entities = [EntityManagerLightEntity(entity_data, coordinator) for entity_data in coordinator.data]
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, "light"))

    # Register your services
    hass.services.async_register(DOMAIN, "create_entity", lambda call: handle_create_entity(call, session), schema=CREATE_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "update_entity", lambda call: handle_update_entity(call, session), schema=UPDATE_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "delete_entity", lambda call: handle_delete_entity(call, session), schema=DELETE_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "set_color", lambda call: handle_set_color(call, session), schema=SET_COLOR_SCHEMA)
    # Register other services similarly

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "session": session
    }

    async def async_close_session(event):
        """Close aiohttp session on shutdown."""
        await session.close()

    hass.bus.async_listen_once("homeassistant_stop", async_close_session)

    return True

async def async_update_data(session):
    """Fetch data from API."""
    async with session.get(f"{API_URL}/entity/") as response:
        if response.status != 200:
            raise UpdateFailed(f"Error fetching data: {response.status}")
        return await response.json()

async def handle_create_entity(call: ServiceCall, session: aiohttp.ClientSession):
    """Handle the service call to create an entity."""
    entity_data = call.data
    try:
        async with session.post(f"{API_URL}/entity/", json=entity_data) as response:
            if response.status == 200:
                # Handle successful response
                response_data = await response.json()
                # Log or perform actions based on the response data
            else:
                # Log or handle the error
                error_message = await response.text()
                _LOGGER.error(f"Failed to create entity: {error_message}")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Error communicating with API: {e}")


async def handle_update_entity(call: ServiceCall, session: aiohttp.ClientSession):
    """Handle the service call to update an entity."""
    entity_data = call.data
    try:
        async with session.put(f"{API_URL}/entity/", json=entity_data) as response:
            if response.status == 200:
                # Handle successful response
                response_data = await response.json()
                # Log or perform actions based on the response data
            else:
                # Log or handle the error
                error_message = await response.text()
                _LOGGER.error(f"Failed to update entity: {error_message}")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Error communicating with API: {e}")

async def handle_delete_entity(call: ServiceCall, session: aiohttp.ClientSession):
    """Handle the service call to delete an entity."""
    entity_id = call.data.get("id")
    try:
        async with session.delete(f"{API_URL}/entity/{entity_id}") as response:
            if response.status == 200:
                # Handle successful response
                _LOGGER.info(f"Entity {entity_id} deleted successfully")
            else:
                # Log or handle the error
                error_message = await response.text()
                _LOGGER.error(f"Failed to delete entity: {error_message}")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Error communicating with API: {e}")

async def handle_set_color(call: ServiceCall, session: aiohttp.ClientSession):
    """Handle the service call to set color of an entity."""
    color_data = call.data
    try:
        async with session.post(f"{API_URL}/color/", json=color_data) as response:
            if response.status == 200:
                # Handle successful response
                _LOGGER.info(f"Color set successfully for entity {color_data.get('entity')}")
            else:
                # Log or handle the error
                error_message = await response.text()
                _LOGGER.error(f"Failed to set color: {error_message}")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Error communicating with API: {e}")

class EntityManagerLightEntity(LightEntity):
    """Representation of an Entity from the external system."""

    def __init__(self, entity_data, coordinator):
        """Initialize the entity."""
        self._entity_data = entity_data
        self.coordinator = coordinator
        self._attr_unique_id = entity_data["id"]
        self._attr_name = entity_data["name"]

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._entity_data["state"]["is_on"]

    async def async_turn_on(self, **kwargs):
        """Turn on the light through the external API."""
        # Prepare the payload or endpoint for turning on the light
        turn_on_data = {
            "entity": self._attr_unique_id,
            "is_on": True,
            # Add other necessary parameters like color, brightness, etc., if applicable
        }

        try:
            async with self.coordinator.session.post(f"{API_URL}/color/", json=turn_on_data) as response:
                if response.status == 200:
                    self._entity_data["state"]["is_on"] = True
                    _LOGGER.info(f"Turned on entity {self._attr_unique_id}")
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
            async with self.coordinator.session.post(f"{API_URL}/color/", json=turn_off_data) as response:
                if response.status == 200:
                    self._entity_data["state"]["is_on"] = False
                    _LOGGER.info(f"Turned off entity {self._attr_unique_id}")
                else:
                    error_message = await response.text()
                    _LOGGER.error(f"Failed to turn off entity: {error_message}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error communicating with API to turn off entity: {e}")


    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()
