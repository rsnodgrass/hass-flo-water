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

    flo = hass[FLO_SERVICE]
    if not flo or not flo.is_connected():
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
        name = f"Flo Water Valve ({location['nickname']})"
        switches.append( FloWaterValve(hass, flo, name, device['id']) )

    add_switches_callback(switches)

class FloWaterValve(FloEntity, ToggleEntity):
    """Flo switch to turn on/off water flow."""

    def __init__(self, hass, flo, name, device_id):
        super().__init__(hass, device_id)
        self._name = name
        self._flo = flo
        self._device_id = device_id
        self.update()

    @property
    def name(self):
        """Inflow control valve switch name"""
        return "{} {}".format("Flo", "Water Control Valve") # FIXME

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
        url = f"{FLO_V2_API_PREFIX}/devices/{self._device_id}"
        self._flo.query(url, extra_params={ "valve": { "target": "open" }})

    def turn_off(self):
        url = f"{FLO_V2_API_PREFIX}/devices/{self._device_id}"
        self._flo.query(url, extra_params={ "valve": { "target": "closed" }})
        
    # NOTE: this updates the data periodically that is cached and shared by ALL sensors/switches
    def update(self):
        device_key = f"flo_device_{self._device_id}"
        data = self._flo.device(self._device_id)
        if data:
            self._hass[device_key] = data
            LOG.info(f"Updated data for device {self._device_id}: {data}")