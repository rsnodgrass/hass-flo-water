"""
Flo Smart Home Water Control System for Home Assistant
See https://github.com/rsnodgrass/hass-flo-water

For good example of update, see Leaf sensor/switch:
https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/nissan_leaf/__init__.py
"""
import logging
import json
import requests
import asyncio
import time
import datetime
import voluptuous as vol

from requests.exceptions import HTTPError, ConnectTimeout
from datetime import datetime, timedelta

from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_EMAIL, CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_SCAN_INTERVAL, ATTR_ATTRIBUTION)
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.config_validation as cv

from .const import FLO_DOMAIN, ATTRIBUTION, ATTR_CACHE, ATTR_COORDINATOR

from pyflowater import PyFlo

LOG = logging.getLogger(__name__)

FLO_SERVICE = 'flo_service'

NOTIFICATION_ID = 'flo_notification'

CONF_LOCATIONS = 'locations'
CONF_LOCATION_ID = 'location_id'

# try to avoid DDoS Flo's cloud service
SCAN_INTERVAL = timedelta(seconds=30)

CONFIG_SCHEMA = vol.Schema({
    FLO_DOMAIN: vol.Schema({
        vol.Optional(CONF_EMAIL): cv.string, # temp optional for backwards compatability
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LOCATIONS, default=[]): cv.ensure_list,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_USERNAME): cv.string # backwards compatibility
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup_entry(hass, entry):
    return

def setup(hass, config):
    """Set up the Flo Water Control System"""

    conf = config.get(FLO_DOMAIN)
    if not conf:
        LOG.error(f"Configuration domain {FLO_DOMAIN} cannot be found in config, ignoring setup!")
        return

    email = conf.get(CONF_EMAIL)
    if not email:
        email = conf.get(CONF_USERNAME)
        LOG.error(f"Deprecated {CONF_USERNAME} key used in flo: config, please change this to {CONF_EMAIL} as this will break in future releases!")

    password = conf.get(CONF_PASSWORD)

    try:
        flo = PyFlo(email, password)
        if not flo.is_connected:
            LOG.error(f"Could not connect to Flo service with {email}")
            return False

        # save password to enable automatic re-authentication while this HA instance is running
        flo.save_password(password)

        hass.data[FLO_SERVICE] = flo
        hass.data[FLO_DOMAIN] = {
            ATTR_CACHE: {},
            ATTR_COORDINATOR: None
        }

    except (ConnectTimeout, HTTPError) as ex:
        LOG.error(f"Unable to connect to Flo service: {str(ex)}")
        hass.components.persistent_notification.create(
            f"Error: {ex}<br />You will need to restart Home Assistant after fixing.",
            title='Flo', notification_id=NOTIFICATION_ID
        )
        return False

    locations = conf.get(CONF_LOCATIONS)

    # if no locations specified, auto discover ALL Flo locations/devices for this account
    if not locations:
        for location in flo.locations():
            locations.append(location['id'])
            LOG.info(
                f"Discovered Flo location {location['id']} ({location['nickname']})")

        if not locations:
            LOG.error(
                f"No device locations returned from Flo service for {email}")
            return True
    else:
        LOG.info(f"Using manually configured Flo locations: {locations}")

    async def async_update_flo_data():
        await hass.async_add_executor_job(update_flo_data)

    def update_flo_data():
        # clear the pyflowater internal cache to force a fresh webservice call
        flo = hass.data[FLO_SERVICE]
        flo.clear_cache()

        cache = hass.data[FLO_DOMAIN][ATTR_CACHE]
        for location in flo.locations():
            cache[location['id']] = location

            # query Flo webservice for each of the devices
            devices = location.get('devices')
            for device in devices:
                device_id = device['id']
                cache[device_id] = flo.device(device_id)


    # create the Flo service update coordinator
    async def async_initialize_coordinator():
        coordinator = DataUpdateCoordinator(
            hass, LOG,
            name=f"Flo Webservice",
            update_method=async_update_flo_data,
            # Set polling interval (will only be polled if there are subscribers)
            update_interval=conf[CONF_SCAN_INTERVAL]
        )
        hass.data[FLO_DOMAIN][ATTR_COORDINATOR] = coordinator
        hass.loop.create_task(coordinator.async_request_refresh())

    # start the coordinator initialiation in the hass event loop
    asyncio.run_coroutine_threadsafe(async_initialize_coordinator(), hass.loop).result()

    # create sensors/switches for all configured locations
    for location_id in locations:
        discovery_info = {CONF_LOCATION_ID: location_id}
        for component in ['sensor', 'switch']:
            discovery.load_platform(
                hass, component, FLO_DOMAIN, discovery_info, config)

    return True


class FloEntity(Entity):
    """Base Entity class for Flo"""

    def __init__(self, hass, name):
        """Store service upon init."""
        #super().(hass)
        self.hass = hass
        self._hass = hass
        self._name = name
        self._state = None
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION
        }

    @property
    def flo_service(self):
        return self._hass.data[FLO_SERVICE]

    @property
    def name(self):
        """Return the display name for this sensor"""
        return self._name

    @property
    def should_poll(self):
        """Flo update coordinator notifies through listener when data has been updated"""
        return True # FIXME: temporarily enable polling until coordinator triggers work

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def state(self):
        return self._state

    def update_state(self, state):
        if state != self._state:
            self._state = state

            unit = ''
            if self.unit_of_measurement:
                unit = self.unit_of_measurement
            LOG.info(f"Updated {self.name} to {self.state} {unit}")

        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._hass.data[FLO_DOMAIN][ATTR_COORDINATOR].async_add_listener(
                self.schedule_update_ha_state(force_refresh=True)
            )
        )


class FloDeviceEntity(FloEntity):
    """Base Entity class for Flo devices"""

    def __init__(self, hass, name, device_id):
        """Store service upon init."""
        super().__init__(hass, name)

        self._device_id = device_id
        self._attrs['device_id'] = device_id

    @property
    def device_state(self):
        """Get device data shared from the Flo update coordinator"""
        return self._hass.data[FLO_DOMAIN][ATTR_CACHE].get(self._device_id)

    def get_telemetry(self, field):
        value = None

        if self.device_state:
            telemetry = self.device_state.get('telemetry')
            if telemetry:
                current_states = telemetry.get('current')
                value = current_states.get(field)

        if not value:
            LOG.warning(
                f"Could not get current {field} from Flo telemetry: {self.device_state}")
        return value


class FloLocationEntity(FloEntity):
    """Base Entity class for Location entities"""

    def __init__(self, hass, name, location_id):
        """Store service upon init."""
        super().__init__(hass, name)

        self._location_id = location_id
        self._attrs['location_id'] = location_id

    @property
    def location_state(self):
        """Get location data shared from the Flo update coordinator"""
        return self._hass.data[FLO_DOMAIN][ATTR_CACHE].get(self._location_id)
