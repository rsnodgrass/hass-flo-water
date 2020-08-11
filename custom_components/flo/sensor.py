"""
Support for Flo water inflow monitoring and control devices

FUTURE:
- convert to async
- should we have a "sensor" that shows whether the Flo device is "online" (e.g. connected to the Flo cloud + WiFi rssi/ssid)
- should this use Flo's every 15-minutes average rollup instead of current telemetry?
- could change to non-polling mode (since the "switch" does the actual polling, these would just update whenever the switch detects a state change)
"""
from datetime import datetime, timedelta
import time
import logging
import voluptuous as vol

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyflowater.const import FLO_MODES
from . import FloEntity, FloDeviceEntity, FloLocationEntity, FLO_DOMAIN, FLO_SERVICE, FLO_CACHE, FLO_ENTITIES, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL=15

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
})

TIME_FMT = '%Y-%m-%dT%H:%M:%S.000Z'

# try to avoid DDoS Flo's cloud service
SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_sensors_callback, discovery_info=None):
    """Setup the Flo water monitoring sensors"""

    flo = hass.data[FLO_SERVICE]
    if flo is None or not flo.is_connected:
        LOG.warning("No connection to Flo service, ignoring setup of platform sensor")
        return False

    if discovery_info:
        location_id = discovery_info[CONF_LOCATION_ID]
    else:  # manual config
        location_id = config[CONF_LOCATION_ID]

    location = flo.location(location_id)
    if not location:
        LOG.warning(f"Flo location {location_id} not found, ignoring creation of Flo sensors")
        return False

    # iterate all devices and create a valve switch for each device
    sensors = []
    for device_details in location['devices']:
        device_id = device_details['id']

        sensors.append( FloRateSensor(hass, device_id))
        sensors.append( FloPressureSensor(hass, device_id))
        sensors.append( FloTempSensor(hass, device_id))

        now = dt_util.utcnow()
        sensors.append( FloConsumptionSensor(hass, "Daily", location_id, device_details,
                        now.replace(hour=0, minute=0, second=0, microsecond=0)))
        sensors.append( FloConsumptionSensor(hass, "Yearly", location_id, device_details,
                        now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)))

        sensors.append( FloMonitoringMode(hass, location_id))

    add_sensors_callback(sensors)



class FloRateSensor(FloDeviceEntity):
    """Water flow rate sensor for a Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, 'Water Flow Rate', device_id)
        self.update()

    @property
    def unit_of_measurement(self):
        """Gallons per minute (gpm)"""
        return 'gpm'

    @property
    def icon(self):
        return 'mdi:water-pump'

    def update(self):
        """Update sensor state"""
        state = self.get_telemetry('gpm')
        if state != None:
            self.update_state( round(state, 1) )

    @property
    def unique_id(self):
        return f"flo_rate_{self._device_id}"


class FloTempSensor(FloDeviceEntity):
    """Water temp sensor for a Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, 'Water Temperature', device_id)
        self.update()

    @property
    def unit_of_measurement(self):
        return TEMP_FAHRENHEIT

    @property
    def icon(self):
        return 'mdi:thermometer'

    def update(self):
        """Update sensor state"""
        state = self.get_telemetry('tempF')
        if state:
            # Flo has (temporarily?) deprecated their temperature API and returns VERY high temps,
            # so DO NOT update the state IF the temperatures are high.
            if int(state) > 140:
                return

            self.update_state(state)

    @property
    def unique_id(self):
        return f"flo_temp_{self._device_id}"


class FloPressureSensor(FloDeviceEntity):
    """Water pressure sensor for a Flo device"""

    def __init__(self, hass, device_id):
        super().__init__(hass, 'Water Pressure', device_id)
        self.update()

    @property
    def unit_of_measurement(self):
        """Pounds per square inch (psi)"""
        return 'psi'

    @property
    def icon(self):
        return 'mdi:gauge'

    def update(self):
        """Update sensor state"""
        state = self.get_telemetry('psi')
        if state:
            self.update_state( round(state, 1) )

    @property
    def unique_id(self):
        return f"flo_pressure_{self._device_id}"


class FloConsumptionSensor(FloDeviceEntity):
    """Water consumption sensor for a Flo device"""

    def __init__(self, hass, period_name, location_id, device_details, startdate):
        super().__init__(hass, f"Water Consumption ({period_name})", device_details['id'])
        self._unique_id = f"flo_consumption_{period_name.lower()}_{self._device_id}_"

        self._location_id = location_id
        self._device_details = device_details
        #self._attrs.update(device_details)

        self._attrs['start_date'] = startdate
        self._last_end = 0

        self.initial_update(startdate)

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
        return round(self._state, 2)

    @property
    def icon(self):
        return "mdi:gauge"

    def readConsumption(self, start, end, interval):
        res = self.flo_service.consumption(self._location_id,
                                           self._device_details['macAddress'],
                                           start.strftime(TIME_FMT),
                                           end.strftime(TIME_FMT),
                                           interval)
        if not res:
            LOG.error(f"Bad Flo consumption response: {start}:{end}:{interval}: %s", res)
            return 0
        return round(res['aggregations']['sumTotalGallonsConsumed'], 1)

    def initial_update(self, startdate):
        """ Initial update sensor state"""
        end = dt_util.utcnow()
        self.update_state(self.readConsumption(startdate, end, '1m'))
        self._total = self._state
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

        self.update_state(state)

    @property
    def unique_id(self):
        return self._unique_id

# FIXME: IDEALLY, Home Assistant would add a new platform for valves (e.g. water_valve, like a water_heater) and this
# should be refactored as an attribute of that.
#
# https://support.meetflo.com/hc/en-us/articles/115003927993-What-s-the-difference-between-Home-Away-and-Sleep-modes-
class FloMonitoringMode(FloLocationEntity):
    """Sensor returning current monitoring mode for the Flo location"""

    def __init__(self, hass, location_id):
        super().__init__(hass, 'Flo Monitoring Mode', location_id)

    @property
    def icon(self):
        return 'mdi:shield-search'

    def update(self):
        """Update sensor state"""
        mode = self.location_state.get('systemMode')
        return self.update_state(mode.get('target'))

    def set_preset_mode(self, mode):
        if not mode in FLO_MODES:
            LOG.info(f"Invalid mode '{mode}' for FloSense monitoring, IGNORING! (valid={FLO_MODES})")
            return

        self.flo_service.set_mode(self._location_id, mode)
        self.update_state(mode)

    @property
    def unique_id(self):
        return f"flo_mode_{self._location_id}"
