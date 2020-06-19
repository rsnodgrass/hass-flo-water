"""
Support for Flo water inflow monitoring and control devices

FUTURE:
- convert to async
- should we have a "sensor" that shows whether the Flo device is "online" (e.g. connected to the Flo cloud + WiFi rssi/ssid)
- should this use Flo's every 15-minutes average rollup instead of current telemetry?
- could change to non-polling mode (since the "switch" does the actual polling, these would just update whenever the switch detects a state change)
"""
from datetime import datetime, timedelta
import logging
import voluptuous as vol

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv

from pyflowater.const import FLO_V2_API_PREFIX, FLO_MODES, FLO_AWAY, FLO_HOME, FLO_SLEEP
from . import FloEntity, FLO_SERVICE, CONF_LOCATION_ID, CONF_STARTDATE

LOG = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string,
    # discovery doesn't seem to like cv.date so use string instead
    vol.Required(CONF_STARTDATE): cv.string
})

TIME_FMT = '%Y-%m-%dT%H:%M:%S.000Z'

# avoid DDoS Flo's cloud service
MIN_SCAN_INTERVAL = 60 # seconds
SCAN_INTERVAL = timedelta(seconds=60)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_sensors_callback, discovery_info=None):
    """Setup the Flo water inflow control sensor"""

    flo = hass.data[FLO_SERVICE]
    if flo is None or not flo.is_connected:
        LOG.warning("No connection to Flo service, ignoring setup of platform sensor")
        return False

    if discovery_info:
        location_id = discovery_info[CONF_LOCATION_ID]
        startdate = discovery_info[CONF_STARTDATE]
    else: # manual config
        location_id = config[CONF_LOCATION_ID]
        startdate = config[CONF_STARTDATE]

    if startdate:
        startdate = datetime.strptime(startdate, '%Y-%m-%d')
    else:
        # take the beginninng of the year
        now = dt_util.utcnow()
        startdate = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        LOG.info(f"No consumption startdate specified...using beginning of the year: {startdate.strftime('%Y-%m-%d')}")

    location = flo.location(location_id)
    if not location:
        LOG.warning(f"Flo location {location_id} not found, ignoring creation of Flo sensors")
        return False

    # iterate all devices and create a valve switch for each device
    sensors = []
    for device_details in location['devices']:
        device_id = device_details['id']

        # the consumption sensor is the coordinator for updating ALL other sensors
        sensors.append( FloConsumptionSensor(hass, flo, location_id, device_details, startdate) )

        sensors.append( FloRateSensor(hass, device_id) )
        sensors.append( FloTempSensor(hass, device_id) )
        sensors.append( FloPressureSensor(hass, device_id) )
        sensors.append( FloMonitoringMode(hass, device_id) )

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
        state = self.get_telemetry('gpm')
        if self._state != state:
            self.update_state(state)
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)

    @property
    def unique_id(self):
        return f"flo_rate_{self._device_id}"

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
        state = self.get_telemetry('tempF')
        if self._state != state:
            self.update_state(state)
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)

    @property
    def unique_id(self):
        return f"flo_temp_{self._device_id}"

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
        state = self.get_telemetry('psi')
        current_state = round(state, 2)
        if state is not None and self._state != current_state:
            self.update_state(current_state)
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)
            
    @property
    def unique_id(self):
        return f"flo_pressure_{self._device_id}"

class FloConsumptionSensor(Entity):
    """Water consumption sensor for a Flo device location"""

    def __init__(self, hass, flo, location_id, device_details, startdate):
        # super().__init__(hass, device_id)
        self._name = "Flo Water Consumption"
        self._state = None
        self._last_end = 0
        self._flo = flo

        self._location_id = location_id
        self._device_details = device_details

        self._attrs = {
            'location_id': location_id,
            'start_date': startdate
        }
        self._attrs.update(device_details)

        self.initial_update(startdate)

    @property
    def name(self):
        """Return the display name for this sensor"""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    @property
    def unit_of_measurement(self):
        """gallons (g)"""
        return "gallons"

    @property
    def state(self):
        """Gallons"""
        return round(self._state, 2)

    @property
    def icon(self):
        return "mdi:gauge"

    def readConsumption(self, start, end, interval):
        res = self._flo.consumption(self._location_id,
                                    self._device_details['macAddress'],
                                    start.strftime(TIME_FMT),
                                    end.strftime(TIME_FMT),
                                    interval)
        if not res:
            LOG.error(f"Bad Flo consumption response: {start}:{end}:{interval}: %s", res)
            return 0
        return round(res['aggregations']['sumTotalGallonsConsumed'], 2)

    def initial_update(self, startdate):
        """ Initial update sensor state"""
        end = dt_util.utcnow()
        self._state = self.readConsumption(startdate, end, '1m')
        self._total = self._state
        LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)
        self._last_end = end

    def update(self):
        """Update sensor state"""
        now = dt_util.utcnow()

        # if we crossed over an hour boundary, add the last hour to the total
        if now.hour != self._last_end.hour:
            end = now.replace(minute=0, second=0, microsecond=0)
            start = end - timedelta(hours=1)
            prev_hour = self.readConsumption(start, end, '1h')
            self._total += prev_hour

        # flo counts all previous consumption in the first second of the hour.
        # don't double count if we are in the 1st second and just crossed over
        if now.hour != self._last_end.hour and now.second == 0:
            curr = 0
        else:
            start = now - timedelta(hours=1)
            curr = self.readConsumption(start, now, '1h')

        self.readConsumption(now - timedelta(days=365), now, '1m')
        state = self._total + curr
        self._last_end = now

        if self._state != state:
            self.update_state(state)
            LOG.info("Updated %s to %f %s", self._name, self._state, self.unit_of_measurement)

        # as the coordinator, always update hte entire device details for debugging purposes
#        self._attrs.update(device_details)
#        self._device_details

    @property
    def unique_id(self):
        return f"flo_consumption_{self._device_details['id']}"


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
            mode = self.device_state['systemMode']
            target = mode.get('target')
            lastKnown = mode.get('lastKnown')
            if target:
                self._mode = target
            elif lastKnown:
                self._mode = lastKnown

        return self._mode

    def set_preset_mode(self, mode):
        if not mode in FLO_MODES:
            LOG.info(f"Invalid mode '{mode}' for FloSense monitoring, ignoring!")
            return

        self._hass.data[FLO_SERVICE].service.set_preset_mode(self._device_id, mode)

        # there may be a delay between when the target mode is set on a Flo device and
        # the actual change in operation. We manually set this.
        self._mode = mode

    @property
    def unique_id(self):
        return f"flo_mode_{self._device_id}"
