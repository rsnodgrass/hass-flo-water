"""
Flo Smart Home Water Control System for Home Assistant
See https://github.com/rsnodgrass/hass-flo-water

For good example of update, see Leaf sensor/switch:
https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/nissan_leaf/__init__.py
"""
import logging
import json
import requests
import time
import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout

from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import ( CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_SCAN_INTERVAL )
import homeassistant.helpers.config_validation as cv

from pyflowater import PyFlo

LOG = logging.getLogger(__name__)

FLO_DOMAIN = 'flo'
FLO_SERVICE = 'flo_service'

NOTIFICATION_ID = 'flo_notification'

CONF_AUTO_DISCOVER = 'discovery'
CONF_LOCATION_ID = 'location_id'

CONFIG_SCHEMA = vol.Schema({
    FLO_DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_AUTO_DISCOVER, default=True): cv.boolean
        #vol.Optional(CONF_LOCATIONS, default=True): cv.list  # locations [ <locationId1>, <locationId2>, ... ]
    })
}, extra=vol.ALLOW_EXTRA)

# cache expiry in minutes; TODO: make this configurable (with a minimum to prevent DDoS)
FLO_CACHE_EXPIRY=10

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

        hass.data[FLO_SERVICE] = flo

    except (ConnectTimeout, HTTPError) as ex:
        LOG.error(f"Unable to connect to Flo service: {str(ex)}")
        hass.components.persistent_notification.create(
            f"Error: {ex}<br />You will need to restart Home Assistant after fixing.",
            title='Flo', notification_id=NOTIFICATION_ID
        )
        return False

    # auto discover and instantiate platforms for all devices and locations
    auto_discover = conf.get(CONF_AUTO_DISCOVER)
    if auto_discover:
        discover_and_create_devices(hass, config, conf)

    # FIXME: allow overriding discover to specify a specific location (or N locations) that are configured...
    #    ... may want to remove discovery config, and always discover unless locations are specified

    return True

def discover_and_create_devices(hass, hass_config, flo_config):
    flo = hass.data[FLO_SERVICE]

    # create sensors and switches for ALL devices at ALL discovered Flo locations
    for location_config in flo.locations():
        platform_config = {
            CONF_LOCATION_ID: location_config['id']
        }
        LOG.info(f"Setting up Flo sensors with config {platform_config}")
    
        for component in ['sensor', 'switch']:
            discovery.load_platform(hass, component, FLO_DOMAIN, platform_config, hass_config)


class FloEntity(Entity):
    """Base Entity class for Flo water inflow control device"""

    def __init__(self, hass, device_id):
        """Store service upon init."""
        self._hass = hass
        self._flo = hass.data[FLO_SERVICE]
        self._device_id = device_id

        self._attrs = {
            'device_id': device_id
        }

        state = self.device_state
        if state:
            self._attrs['nickname'] = state['nickname']
            self._name = 'Flo (' + self._attrs['nickname'] + ')'
        else:
            self._attrs['nickname'] = 'Flo Water'
            self._name = self._attrs['nickname'] # default if unspecified

    @property
    def name(self):
        """Return the display name for this sensor"""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def device_state(self):
        device_key = f"flo_device_{self._device_id}"
        return self._hass.data[device_key]

    def get_telemetry(self, field):
        if self.device_state:
            telemetry = self.device_state['telemetry']
            current_states = telemetry['current']
            return current_states[field]
        else:
            return None
