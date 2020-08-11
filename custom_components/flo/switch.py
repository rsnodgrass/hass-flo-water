"""
Support for Flo Water Control System inflow control device valve on/off
"""
import logging
import pprint
import voluptuous as vol
from datetime import timedelta

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

from . import FloDeviceEntity, FLO_DOMAIN, FLO_SERVICE, FLO_CACHE, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

# default to 1 minute, don't DDoS Flo servers
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

# pylint: disable=unused-argument
# NOTE: there is a platform loaded for each LOCATION (not device, which there may be multiple devices)


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
        switches.append(FloWaterValve(hass, device['id']))

    add_switches_callback(switches)


class FloWaterValve(FloDeviceEntity, ToggleEntity):
    """Flo switch to turn on/off water flow."""

    def __init__(self, hass, device_id):
        super().__init__(hass, 'Flo Water Valve', device_id)

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
        self.flo_service.turn_valve_on(self._device_id)

         # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be on (eventually)
        self.update_state(True)

    def turn_off(self):
        self.flo_service.turn_valve_off(self._device_id)

         # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be off (eventually)
        self.update_state(False)

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
