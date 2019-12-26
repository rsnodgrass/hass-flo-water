"""
Support for Flo Water Control System inflow control device valve on/off
"""
import logging
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
 
        self.update()
        state = self.device_state
        if state:
            self._attrs['nickname'] = state['nickname']

    @property
    def is_on(self):
        """Return true if Flo control valve is on."""
        if self.device_state:
            valve = self.device_state['valve']
            return valve['lastKnown'] == 'open'
        else:
            # FIXME: we assume the valve is on IF we cannot connect to the Flo service
            return True

    def turn_on(self):
        self._flo.turn_valve_on(self._device_id)

    def turn_off(self):
        self._flo.turn_valve_off(self._device_id)
        
    # NOTE: this updates the data periodically that is cached and shared by ALL sensors/switches
    def update(self):
        device_key = f"flo_device_{self._device_id}"
        data = self._flo.device(self._device_id)
        if data:
            self._hass.data[device_key] = data
            LOG.info(f"Updated data for device {self._device_id}: {data}")