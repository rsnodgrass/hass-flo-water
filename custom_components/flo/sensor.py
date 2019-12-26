"""
Support for Flo water inflow monitoring and control devices

FUTURE:
- convert to async
- should we have a "sensor" that shows whether the Flo device is "online" (e.g. connected to the Flo cloud + WiFi rssi/ssid)
- should this use Flo's every 15-minutes average rollup instead of current telemetry?
- could change to non-polling mode (since the "switch" does the actual polling, these would just update whenever the switch detects a state change)
"""
import logging
import json
import voluptuous as vol
import pprint

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

from pyflowater.const import FLO_V2_API_PREFIX, FLO_MODES, FLO_AWAY, FLO_HOME, FLO_SLEEP
from . import FloEntity, FLO_SERVICE, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

ATTR_TIME       = 'time'
ATTR_TOTAL_FLOW = 'total_flow'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

# pylint: disable=unused-argument
def setup_platform(hass, config, add_sensors_callback, discovery_info=None):
    """Setup the Flo water inflow control sensor"""

    flo = hass.data[FLO_SERVICE]
    if flo == None or not flo.is_connected:
        LOG.warning("No connection to Flo service, ignoring setup of platform sensor")
        return False

    pp = pprint.PrettyPrinter(indent=4)
    LOG.info(f"Discovery {pp.pprint(discovery_info)}")

    if discovery_info:
        location_id = discovery_info[CONF_LOCATION_ID]
    else: # manual config
        location_id = config[CONF_LOCATION_ID]

    location = flo.location(location_id)
    if not location:
        LOG.warning(f"Flo location {location_id} not found, ignoring creation of Flo sensors")
        return False

    # iterate all devices and create a valve switch for each device
    sensors = []
    for device in location['devices']:
        device_id = device['id']
        
        sensors.append( FloRateSensor(hass, device_id) )
        sensors.append( FloTempSensor(hass, device_id) )
        sensors.append( FloPressureSensor(hass, device_id) )
        sensors.append( FloMonitoringMode(hass, device_id) )

    for sensor in sensors:
        sensor.update()

    add_sensors_callback(sensors)

# pylint: disable=too-many-instance-attributes
class FloRateSensor(FloEntity):
    """Water flow rate sensor for a Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, device_id)
        self._name = 'Flo Water Flow Rate'
        self._state = None
        self.update()

    @property
    def unit_of_measurement(self):
        """Gallons per minute (gpm)"""
        return 'gpm'

    @property
    def state(self):
        """Water flow rate"""
        return self._state

    @property
    def icon(self):
        return 'mdi:water-pump'

    def update(self):
        """Update sensor state"""
        state = float(self.get_telemetry('gpm'))
        if self._state != state:
            self._state = state
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)

class FloTempSensor(FloEntity):
    """Water temp sensor for a Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, device_id)
        self._name = 'Flo Water Temperature'
        self._state = None
        self.update()

    @property
    def unit_of_measurement(self):
        return TEMP_FAHRENHEIT

    @property
    def state(self):
        """Water temperature"""
        return self._state

    @property
    def icon(self):
        return 'mdi:thermometer'

    def update(self):
        """Update sensor state"""
        state = float(self.get_telemetry('tempF'))
        if self._state != state:
            self._state = state
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)


class FloPressureSensor(FloEntity):
    """Water pressure sensor for a Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, device_id)
        self._name = 'Flo Water Pressure'
        self._state = None
        self.update()

    @property
    def unit_of_measurement(self):
        """Pounds per square inch (psi)"""
        return 'psi'

    @property
    def state(self):
        """Water pressure"""
        return self._state

    @property
    def icon(self):
        return 'mdi:gauge'

    def update(self):
        """Update sensor state"""
        state = float(self.get_telemetry('psi'))
        if self._state != state:
            self._state = state
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)

# https://support.meetflo.com/hc/en-us/articles/115003927993-What-s-the-difference-between-Home-Away-and-Sleep-modes-
class FloMonitoringMode(FloEntity):
    """Sensor returning current monitoring mode for the Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, device_id)
        self._name = 'Flo Monitoring Mode'
        self._mode = None
        self.update()

    @property
    def unit_of_measurement(self):
        """Monitoring mode"""
        return 'mode'

    @property
    def state(self):
        """Flo monitoring mode: home, away, sleep"""
        return self._mode

    @property
    def icon(self):
        return 'mdi:shield-search'

    def update(self):
        """Update sensor state"""
        if self.device_state:
            systemMode = self.device_state['systemMode']
            self._mode = systemMode['lastKnown']
            return self._mode
        else:
            return self._mode

    def set_preset_mode(self, mode):
        self._hass.data[FLO_SERVICE].service.set_preset_mode(self._device_id, mode)

        # NOTE: there may be a delay between when the target mode is set on a Flo device and
        # the actual change in operation. We manually set this.
        self._mode = mode
