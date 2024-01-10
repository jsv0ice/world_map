import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import LightEntity
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import _LOGGER
import logging
import sys
import os

currentdir = os.path.dirname(os.path.abspath(__file__))
libs_path = os.path.join(currentdir, 'libs')
sys.path.insert(0, libs_path)

import socketio

DOMAIN = "world_map_entity_manager"

_LOGGER = logging.getLogger(__name__)

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

async def async_setup_websocket(hass: HomeAssistant, host, port):
    sio = socketio.AsyncClient(logger=_LOGGER)

    @sio.event
    async def connect():
        _LOGGER.info("Connected to WebSocket Server")

    @sio.event
    async def disconnect():
        _LOGGER.info("Disconnected from WebSocket Server")

    try:
        await sio.connect(f'ws://{host}:{port}', namespaces=['/ws-color'])
        return sio
    except Exception as e:
        _LOGGER.error(f"Failed to establish WebSocket connection: {e}")
        return None

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the component."""

    # Create an aiohttp session for HTTP requests
    session = aiohttp.ClientSession()

    conf = config.get(DOMAIN)

    host = conf.get("host")
    port = conf.get("port")
   
    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name="world_map_entity_manager",
        update_method=lambda: async_update_data(hass),
        update_interval=timedelta(minutes=5),
    )

    # Setup WebSocket connection
    websocket_client = await async_setup_websocket(hass, host, port)

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "session": session,
        "API_URL": f"http://{host}:{port}",
        "websocket": websocket_client
    }

    await coordinator.async_refresh()

    if coordinator.data is not None:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform('light', DOMAIN, {}, config)
        )

    # Register your services
    hass.services.async_register(DOMAIN, "create_entity", lambda call: handle_create_entity(call, session, hass), schema=CREATE_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "update_entity", lambda call: handle_update_entity(call, session, hass), schema=UPDATE_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "delete_entity", lambda call: handle_delete_entity(call, session, hass), schema=DELETE_ENTITY_SCHEMA)
    hass.services.async_register(DOMAIN, "set_color", lambda call: handle_set_color(call, hass), schema=SET_COLOR_SCHEMA)
    # Register other services similarly

    async def async_close_websocket(event):
        """Close WebSocket connection on shutdown."""
        websocket_client = hass.data[DOMAIN]["websocket"]
        if websocket_client:
            await websocket_client.disconnect()

    hass.bus.async_listen_once("homeassistant_stop", async_close_websocket)

    return True

async def async_update_data(hass: HomeAssistant):
    """Fetch data from API."""
    api_url = hass.data[DOMAIN]["API_URL"]
    session = hass.data[DOMAIN]["session"] 

    async with session.get(f"{api_url}/entity/") as response:
        if response.status != 200:
            _LOGGER.error(f"Failed to fetch data: {response.status}")
            raise UpdateFailed(f"Error fetching data: {response.status}")
        data = await response.json()
        _LOGGER.debug(f"Fetched data: {data}")
        return data

async def handle_create_entity(call: ServiceCall, session: aiohttp.ClientSession, hass: HomeAssistant):
    """Handle the service call to create an entity."""
    entity_data = call.data
    api_url = hass.data[DOMAIN]["API_URL"]  # Access API_URL from hass.data

    try:
        async with session.post(f"{api_url}/entity/", json=entity_data) as response:
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

async def handle_update_entity(call: ServiceCall, session: aiohttp.ClientSession, hass: HomeAssistant):
    """Handle the service call to update an entity."""
    entity_data = call.data
    api_url = hass.data[DOMAIN]["API_URL"]  # Access API_URL from hass.data
    try:
        async with session.put(f"{api_url}/entity/", json=entity_data) as response:
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

async def handle_delete_entity(call: ServiceCall, session: aiohttp.ClientSession, hass: HomeAssistant):
    """Handle the service call to delete an entity."""
    entity_id = call.data.get("id")
    api_url = hass.data[DOMAIN]["API_URL"]  # Access API_URL from hass.data
    try:
        async with session.delete(f"{api_url}/entity/{entity_id}") as response:
            if response.status == 200:
                # Handle successful response
                _LOGGER.info(f"Entity {entity_id} deleted successfully")
            else:
                # Log or handle the error
                error_message = await response.text()
                _LOGGER.error(f"Failed to delete entity: {error_message}")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Error communicating with API: {e}")

async def handle_set_color(call: ServiceCall, session: aiohttp.ClientSession, hass: HomeAssistant):
    """Handle the service call to set color of an entity."""
    color_data = call.data
    api_url = hass.data[DOMAIN]["API_URL"]  # Access API_URL from hass.data
    try:
        async with session.post(f"{api_url}/color/", json=color_data) as response:
            if response.status == 200:
                # Handle successful response
                _LOGGER.info(f"Color set successfully for entity {color_data.get('entity')}")
            else:
                # Log or handle the error
                error_message = await response.text()
                _LOGGER.error(f"Failed to set color: {error_message}")
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Error communicating with API: {e}")