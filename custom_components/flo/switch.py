"""
Support for Flo Water Control System inflow control device valve on/off switches

SWITCHES:
mode (home/away/sleep) ... not a switch
"""
import logging

from homeassistant.helpers.entity import ToggleEntity
from . import FloEntity, FLO_DOMAIN, FLO_SERVICE, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

# pylint: disable=unused-argument
# NOTE: there is a platform loaded for each LOCATION (not device, which there may be multiple devices)
def setup_platform(hass, config, add_switches_callback, discovery_info=None):
    """Setup the Flo Water Control System integration."""

    flo = hass[FLO_SERVICE]
    if not flo or not flo.service.is_connected():
        LOG.warning("No connection to Flo service, ignoring setup of platform sensor")
        return False

    switches = []
    switches.append( FloControlSwitch(None) ) # FIXME
    add_switches_callback(switches)

class FloControlSwitch(FloEntity, ToggleEntity):
    """Flo control switch to turn on/off water flow."""

    @property
    def name(self):
        """Inflow control valve switch name"""
        return "{} {}".format("Flo", "Water Control Valve") # FIXME
   
    @property
    def is_on(self):
        """Return true if Flo control valve is on."""
        return True # FIXME
