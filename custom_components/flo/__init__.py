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
        pyflo_api = PyFlo(username, password)
        if not pyflo_api.is_connected():
            LOG.error(f"Could not connect to Flo service with user {username}")
            return False

        hass.data[FLO_SERVICE] = FloService(pyflo_api)

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

def discover_and_create_devices(hass, hass_config, conf):
    flo = hass.data[FLO_SERVICE]

    # create sensors and switches for ALL devices at ALL discovered Flo locations
    for location_config in flo.service.locations():
        platform_config = {
            CONF_LOCATION_ID: location_config['id']
        }
        for component in ['sensor', 'switch']:
            discovery.load_platform(hass, component, FLO_DOMAIN, platform_config, hass_config)


class FloEntity(Entity):
    """Base Entity class for Flo water inflow control device"""

    def __init__(self, hass):
        """Store service upon init."""
        self._flo_service = hass.data[FLO_SERVICE]
        self._attrs = {}

        if self._name is None:
            self._name = 'Flo Water' # default if unspecified

    @property
    def name(self):
        """Return the display name for this sensor"""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

class FloService:
    """Client interface to the Flo service API (adds caching over raw PyFlo service API)"""

    def __init__(self, pyflo_api):
        self._pyflo_api = pyflo_api
        self._last_waterflow_measurement = None
        self._last_waterflow_update = 0

    @property
    def service(self):
        return self._pyflo_api

    # FIXME: cache the initial configuration...for now, the only refresh of Flo devices is to restart HA

    def get_waterflow_measurement(self, flo_icd_id):
        """Fetch latest state for a Flo inflow control device"""

        # to avoid DDoS Flo's servers, cache any results loaded in last 10 minutes
        now = int(time.time())
        if self._last_waterflow_update > (now - (FLO_CACHE_EXPIRY * 60)):
            LOG.debug("Using cached waterflow measurements (expiry %d min): %s",
                      FLO_CACHE_EXPIRY, self._last_waterflow_measurement)
            return self._last_waterflow_measurement

        # request data for the last 30 minutes, plus Flo API takes ms since epoch
        timestamp = (now - ( 60 * 30 )) * 1000

        waterflow_url = '/waterflow/measurement/icd/' + flo_icd_id + '/last_day?from=' + str(timestamp)
        response = self.service.query(waterflow_url, method='GET')
        # Example response: [ {
        #    "average_flowrate": 0,
        #    "average_pressure": 86.0041294012751,
        #    "average_temperature": 68,
        #    "did": "606405bfe487",
        #    "total_flow": 0,
        #    "time": "2019-05-30T07:00:00.000Z"
        #  }, {}, ... ]
        json_response = response.json()

        # Return the latest measurement data point. Strangely Flo's response list includes stubs
        # for timestamps in the future, so this searches for the last non-0.0 pressure entry
        # since the pressure always has a value even when the Flo valve is shut off.
        latest_measurement = json_response[0]
        for measurement in json_response:
            if measurement['average_pressure'] <= 0.0:
                continue

            if measurement['time'] > latest_measurement['time']:
                latest_measurement = measurement

        mutex.acquire()
        try:
            self._last_waterflow_measurement = latest_measurement
            self._last_waterflow_update = now
        finally:
            mutex.release()
    
        return latest_measurement

    @property
    def unit_system(self):
        """Return user configuration, such as units"""

        # FIXME: cache!
        response = self.service.query('/userdetails/me', method='GET')
 
        # Example response: {
        #    "firstname": "Jenny",
        #    "lastname": "Tutone",
        #    "phone_mobile": "8008675309",
        #    "user_id": "7cab21-d488-3213-af31-c1ca20177b5a",
        #    "unit_system": "imperial_us"
        #  }
        json_response = response.json()
        return json_response['unit_system']