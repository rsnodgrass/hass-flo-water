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
    if not flo or not flo.service.is_connected():
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
        super().__init__(hass)
        self._name = name
        self._flo = flo
        self._device_id = device_id

    @property
    def name(self):
        """Inflow control valve switch name"""
        return "{} {}".format("Flo", "Water Control Valve") # FIXME

    @property
    def is_on(self):
        """Return true if Flo control valve is on."""
        return True # FIXME

    def turn_on(self):
        open_valve = '{"valve":{"target":"open"}}'

        url = f"{FLO_V2_API_PREFIX}/devices/{self._device_id}"
        #https://api-gw.meetflo.com/api/v2/devices/<deviceId>
        self._flo.query()

    def turn_off(self):
        close_valve = '{"valve":{"target":"closed"}}'