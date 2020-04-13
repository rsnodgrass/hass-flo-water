"""
Support for Flo Water Control System inflow control device valve on/off
"""
import logging
import pprint
import voluptuous as vol

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

from pyflowater.const import FLO_V2_API_PREFIX
from . import FloEntity, FLO_DOMAIN, FLO_SERVICE, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

# pylint: disable=unused-argument
# NOTE: there is a platform loaded for each LOCATION (not device, which there may be multiple devices)
def setup_platform(hass, config, add_switches_callback, discovery_info=None):
    """Setup the Flo Water Control System integration."""

    flo = hass.data[FLO_SERVICE]
    if flo == None or not flo.is_connected:
        LOG.warning("No connection to Flo service, ignoring setup of platform sensor")
        return False

    if discovery_info:
        location_id = discovery_info[CONF_LOCATION_ID]
    else: # manual config
        location_id = config[CONF_LOCATION_ID]

    location = flo.location(location_id)
    if not location:
        LOG.warning(f"Flo location {location_id} not found, ignoring creation of Flo control valves")
        return False

    # iterate all devices and create a valve switch for each device
    switches = []
    for device in location['devices']:
        switches.append( FloWaterValve(hass, flo, device['id']) )

    add_switches_callback(switches)

class FloWaterValve(FloEntity, ToggleEntity):
    """Flo switch to turn on/off water flow."""

    def __init__(self, hass, flo, device_id):
        super().__init__(hass, device_id)
        self._flo = flo
        self._name = 'Flo Water Valve'
        self._is_open = True # default to being open

        self.update()
        state = self.device_state
        if state:
            self._attrs['nickname'] = state['nickname']

    @property
    def icon(self):
        if self.is_on:
            return 'mdi:valve-open'
        else:
            return 'mdi:valve-closed'

    @property
    def is_on(self):
        """Return true if Flo control valve is on."""
        return self._is_open

    def turn_on(self):
        self._flo.turn_valve_on(self._device_id)
        self._is_open = True

    def turn_off(self):
        self._flo.turn_valve_off(self._device_id)
        self._is_open = False
        
    # NOTE: this updates the data periodically via polling, caches the results which are then shared by ALL sensors/switches
    def update(self):
        # clear the cache ONCE per scan interval to force updates
        # (the other sensors/switches read the latest cached data)
        # TODO: make this more efficient rather than clear EVERY time
        self._flo.clear_cache()

        # call the Flo cloud service
        data = self._flo.device(self._device_id)
        if data:
            self._hass.data[self.device_key] = data
            valve = data['valve']
            target = valve.get('target')
            lastKnown = valve.get('lastKnown')

            if target:
                self._is_open = target == 'open'
            elif lastKnown:
                self._is_open = lastKnown == 'open'
            else:
#                LOG.debug(f"Could not update valve state for device {self._device_id}: %s / {valve}", pprint.pformat(data))
                return

            LOG.info(f"Updated latest Flo system mode info {valve} for {self._device_id}" )

        else:
            LOG.error(f"Could not get state for device {self._device_id}")

    @property
    def unique_id(self):
        return f"flo_valve_{self._device_id}"
