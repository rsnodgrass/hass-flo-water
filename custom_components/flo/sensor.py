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

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, ATTR_ENTITY_ID
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from pyflowater.const import FLO_MODES
from . import FloEntity, FloDeviceEntity, FloLocationEntity, FLO_DOMAIN, FLO_SERVICE, FLO_CACHE, FLO_ENTITIES, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

TIME_FMT = '%Y-%m-%dT%H:%M:%S.000Z'

ATTR_MODE = 'mode'

SERVICE_SET_MODE = 'set_mode'
SERVICE_SET_MODE_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.time_period,
    vol.Required(ATTR_MODE): vol.In(FLO_MODES)
}
SERVICE_SET_MODE_SIGNAL = f"{SERVICE_SET_MODE}_%s"

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

    sensors = []
    mode_sensors = {}

    # create location-based sensors
    device_details = location['devices'][0]
    now = dt_util.utcnow()

    # FIXME: set the update period for the daily sensor to no less than 5 minutes!!!
    sensors.append( FloConsumptionSensor(hass, "Daily", location_id, device_details,
                    now.replace(hour=0, minute=0, second=0, microsecond=0)))

    # FIXME: set the update period for the yearly sensor to no less than hourly!!!
    sensors.append( FloConsumptionSensor(hass, "Yearly", location_id, device_details,
                    now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)))

    # create device-based sensors for all devices at this location
    for device_details in location['devices']:
        device_id = device_details['id']

        sensors.append( FloRateSensor(hass, device_id))
        sensors.append( FloPressureSensor(hass, device_id))
        sensors.append( FloTempSensor(hass, device_id))

    # add sensor that tracks the current monitoring mode for a location
    mode_sensor = FloMonitoringMode(hass, location_id)
    sensors.append( mode_sensor )
    mode_sensors[mode_sensor.entity_id] = mode_sensor

    add_sensors_callback(sensors)

    # register any exposed services
    def service_set_mode(call):
        entity = mode_sensors[ call.data[ATTR_ENTITY_ID] ]
        mode = call.data[ATTR_MODE]
        if entity:
            entity.set_mode(mode)

    hass.services.register(FLO_DOMAIN, SERVICE_SET_MODE, service_set_mode, SERVICE_SET_MODE)

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


# FIXME: This could use reworking and optimization, especially with multiple periods intervals now
class FloConsumptionSensor(FloDeviceEntity):
    """Water consumption sensor for a Flo device"""

    def __init__(self, hass, period_name, location_id, device_details, startdate):
        super().__init__(hass, f"Water Consumption ({period_name})", device_details['id'])
        self._unique_id = f"flo_consumption_{period_name.lower()}_{self._device_id}"

        self._location_id = location_id
        self._device_details = device_details
        #self._attrs.update(device_details)

        self._attrs['start_date'] = startdate
        self._last_end = 0

        self._interval = '1h'
        # FIXME: throttle based on time interval analyzed (e.g. 60 seconds for hourly, hourly for yearly)

        self.initial_update(startdate)

    @property
    def should_poll(self):
        # FIXME: how should this update, should there be a coordinator
        return True

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
            prev_hour = self.readConsumption(start, end, self._interval)
            self._total += prev_hour

        # flo counts all previous consumption in the first second of the hour.
        # don't double count if we are in the 1st second and just crossed over
        if now.hour != self._last_end.hour and now.second == 0:
            curr = 0
        else:
            start = now - timedelta(hours=1)
            curr = self.readConsumption(start, now, self._interval)

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

    def set_mode(self, mode):
        if not mode in FLO_MODES:
            LOG.info(f"Invalid Flo location monitoring mode '{mode}', IGNORING! (valid={FLO_MODES})")
            return

        self.flo_service.set_mode(self._location_id, mode)
        self.update_state(mode)

    async def async_added_to_hass(self):
        """Run when entity is about to be added to hass."""
        async_dispatcher_connect(
            self.hass,
            SERVICE_SET_MODE_SIGNAL.format(self.entity_id),
            self.SET_mode
        )

    @property
    def unique_id(self):
        return f"flo_mode_{self._location_id}"
    