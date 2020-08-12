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

from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_SCAN_INTERVAL, ATTR_ATTRIBUTION)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyflowater import PyFlo

LOG = logging.getLogger(__name__)

FLO_DOMAIN = 'flo'
FLO_SERVICE = 'flo_service'
FLO_CACHE = 'flo_cache'

NOTIFICATION_ID = 'flo_notification'

CONF_LOCATIONS = 'locations'
CONF_LOCATION_ID = 'location_id'

ATTRIBUTION = 'Data provided by Flo'

# try to avoid DDoS Flo's cloud service
DEFAULT_SCAN_INTERVAL=15
SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SIGNAL_FLO_DATA_UPDATE = "flo_data_update_%s"

CONFIG_SCHEMA = vol.Schema({
    FLO_DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LOCATIONS, default=[]): cv.ensure_list,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    """Set up the Flo Water Control System"""

    conf = config[FLO_DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        flo = PyFlo(username, password)
        if not flo.is_connected:
            LOG.error(f"Could not connect to Flo service with user {username}")
            return False

        # save password to enable automatic re-authentication while this HA instance is running
        flo.save_password(password)

        hass.data[FLO_SERVICE] = flo
        hass.data[FLO_CACHE] = {}
        hass.data[FLO_DOMAIN] = {}

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
            LOG.info(f"Discovered Flo location {location['id']} ({location['nickname']})")

        if not locations:
            LOG.error(f"No device locations returned from Flo service for user {username}")
            return True
    else:
        LOG.info(f"Using manually configured Flo locations: {locations}")

    # create coordinator to update data from Flo webservice and fetch initial data so data is available immediately
    future = asyncio.run_coroutine_threadsafe( FloDataUpdateCoordinator.initialize(hass), hass.loop )
    if future.result():
        LOG.debug("Initialization of Flo coordinator complete")

    # create sensors/switches for all configured locations
    for location_id in locations:
        discovery_info = { CONF_LOCATION_ID: location_id }
        for component in ['sensor', 'switch']:
            discovery.load_platform(
                hass, component, FLO_DOMAIN, discovery_info, config)

    return True


class FloDataUpdateCoordinator(DataUpdateCoordinator):
    @staticmethod
    async def initialize(hass):
        """Required since DataUpdateCoordinator constructor must be run in event loop (and platform is non-async)"""
        # create coordinator to update data from Flo webservice and fetch initial data so data is available immediately
        coordinator = FloDataUpdateCoordinator(hass)
        hass.data[FLO_DOMAIN]['coordinator'] = coordinator
        LOG.debug("Initialized the coordinator")
        await coordinator.async_refresh()
        return coordinator

    def __init__(self, hass):
        super().__init__(
            hass, LOG, name=FLO_DOMAIN, update_interval=SCAN_INTERVAL
        )

        self._hass = hass
        self._hass.data[FLO_CACHE] = {}

    async def _async_update_data(self):
        LOG.debug("Calling sync executor self._update_data")
        await self._hass.async_add_executor_job(self._update_data)

    def _update_data(self):
        LOG.debug(f"Coordinator calling Flo webservice for latest state")
        flo = self._hass.data[FLO_SERVICE]

        # clear the pyflowater internal cache to force a fresh webservice call
        flo.clear_cache()

        cache = self._hass.data[FLO_CACHE]
        for location in flo.locations():
            cache[location['id']] = location

            # notify all entities using cached location data than an update occurred
            async_dispatcher_send(self._hass, SIGNAL_FLO_DATA_UPDATE.format(location['id']))

            # query Flo webservice for each of the devices
            devices = location.get('devices')
            for device in devices:
                device_id = device['id']
                cache[device_id] = flo.device(device_id)

                # notify all entities using cached device data than an update occurred
                async_dispatcher_send(self._hass, SIGNAL_FLO_DATA_UPDATE.format(device_id))

        return True



class FloEntity(Entity):
    """Base Entity class for Flo"""

    def __init__(self, hass, name):
        """Store service upon init."""
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
        """Flo update coordinator notifies an update needs to occur via signal notifications (SIGNAL_FLO_DATA_UPDATE)"""
        return False

    def _trigger_update_callback(self):
        self.schedule_update_ha_state(force_refresh=True)

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

        # for debugging, mark last_updated with current timestamp
        if self._attrs:
            now = datetime.now()
            self._attrs['last_updated'] = now.strftime("%m/%d/%Y %H:%M:%S")


class FloDeviceEntity(FloEntity):
    """Base Entity class for Flo devices"""

    def __init__(self, hass, name, device_id):
        """Store service upon init."""
        super().__init__(hass, name)

        self._device_id = device_id
        self._attrs ['device_id'] = device_id

    @property
    def device_state(self):
        """Get device data shared from the Flo update coordinator"""
        return self._hass.data[FLO_CACHE].get(self._device_id)

    def get_telemetry(self, field):
        value = None

        if self.device_state:
            telemetry = self.device_state.get('telemetry')
            if telemetry:
                current_states = telemetry.get('current')
                value = current_states.get(field)

        if not value:
            LOG.warning(f"Could not get current {field} from Flo telemetry: {self.device_state}")
        return value

    async def async_added_to_hass(self):
        """Run when entity is about to be added to hass."""
        # register this entity to listen to updates for this device
        async_dispatcher_connect( self.hass, SIGNAL_FLO_DATA_UPDATE.format(self._device_id), self.update )


class FloLocationEntity(FloEntity):
    """Base Entity class for Location entities"""

    def __init__(self, hass, name, location_id):
        """Store service upon init."""
        super().__init__(hass, name)

        self._location_id = location_id
        self._attrs['location_id'] = location_id

    @property
    def location_state(self):
        """Get device data shared from the Flo update coordinator"""
        return self._hass.data[FLO_CACHE].get(self._location_id)

    async def async_added_to_hass(self):
        """Run when entity is about to be added to hass."""
        # register this entity to listen to updates for this location
        async_dispatcher_connect( self.hass, SIGNAL_FLO_DATA_UPDATE.format(self._location_id), self.update )
