"""
Support for Flo Water Control System inflow control device valve on/off
"""
import logging
import asyncio
import voluptuous as vol
from datetime import timedelta

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from homeassistant.const import ATTR_ENTITY_ID

from . import (
    FloDeviceEntity,
    FLO_DOMAIN,
    FLO_SERVICE,
    FLO_CACHE,
    CONF_LOCATION_ID
)

LOG = logging.getLogger(__name__)

# default to 1 minute, don't DDoS Flo servers
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

SERVICE_RUN_HEALTH_TEST = 'run_health_test'
SERVICE_RUN_HEALTH_TEST_SCHEMA = { vol.Required(ATTR_ENTITY_ID): cv.time_period }
SERVICE_RUN_HEALTH_TEST_SIGNAL = f"{SERVICE_RUN_HEALTH_TEST}_%s"

# pylint: disable=unused-argument
def setup_platform(hass, config, add_switches_callback, discovery_info=None):
    """Setup the Flo Water Control System integration."""

    flo = hass.data[FLO_SERVICE]
    if flo == None or not flo.is_connected:
        LOG.warning("No connection to Flo service, ignoring platform setup")
        return False

    if discovery_info:
        location_id = discovery_info[CONF_LOCATION_ID]
    else:  # manual config
        location_id = config[CONF_LOCATION_ID]

    location = flo.location(location_id)
    if not location:
        LOG.warning(f"Flo location {location_id} not found, ignoring creation of Flo control valves")
        return False

    # iterate all devices and create a valve switch for each device
    switches = []
    for device in location['devices']:
        valve = FloWaterValve(hass, device['id'])
        switches.append(valve)

    add_switches_callback(switches)
            
    # register any exposed services
    # NOTE: would have used async_register_entity_service if this platform setup was async

    def service_run_health_test(call):
        entity_id = call.data[ATTR_ENTITY_ID]
        async_dispatcher_send(hass, SERVICE_RUN_HEALTH_TEST_SIGNAL.format(entity_id))
    hass.services.register(FLO_DOMAIN, SERVICE_RUN_HEALTH_TEST, service_run_health_test, SERVICE_RUN_HEALTH_TEST_SCHEMA)

class FloWaterValve(FloDeviceEntity, ToggleEntity):
    """Flo switch to turn on/off water flow."""

    def __init__(self, hass, device_id):
        super().__init__(hass, 'Water Valve', device_id)

        state = self.device_state
        if state:
            self._attrs['nickname'] = state['nickname']
            self.update()
 
    @property
    def icon(self):
        if self.state == True:
            return 'mdi:valve-open'
        else:
            return 'mdi:valve-closed'

    @property
    def is_on(self):
        """Return true if Flo control valve is open."""
        return self.state == True

    def turn_on(self):
        self.flo_service.open_valve(self._device_id)

         # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be on (eventually)
        self.update_state(True)
        # FIXME: trigger update coordinator to read latest state from service

    def turn_off(self):
        self.flo_service.close_valve(self._device_id)

        # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be off (eventually)
        self.update_state(False)
        # FIXME: trigger update coordinator to read latest state from service

    def run_health_test(self):
        """Run a health test."""
        self.flo_service.run_health_test(self._device_id)

    async def async_added_to_hass(self):
        """Run when entity is about to be added to hass."""
        async_dispatcher_connect(
            self.hass,
            SERVICE_RUN_HEALTH_TEST_SIGNAL.format(self.entity_id),
            self.run_health_test
        )

    def update(self):
        if not self.device_state:
            return

        valve = self.device_state.get('valve')
        if valve:
            target = valve.get('target')
            lastKnown = valve.get('lastKnown')

            if target:
                self.update_state( target == 'open' )
            elif lastKnown:
                self.update_state( lastKnown == 'open' )

    @property
    def unique_id(self):
        return f"flo_valve_{self._device_id}"
