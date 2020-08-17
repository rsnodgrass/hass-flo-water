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

from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, ATTR_ENTITY_ID, DEVICE_CLASS_PRESSURE, DEVICE_CLASS_TEMPERATURE
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from pyflowater.const import FLO_MODES
from .const import ICON_FLOW_RATE, ICON_TEMP, ICON_CONSUMPTION, ICON_PRESSURE, ICON_MONITORING

from . import FloEntity, FloDeviceEntity, FloLocationEntity, FLO_DOMAIN, FLO_SERVICE, CONF_LOCATION_ID

LOG = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

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

    # create device-based sensors for all devices at this location
    for device_details in location['devices']:
        device_id = device_details['id']

        sensors.append( FloRateSensor(hass, device_id))
        sensors.append( FloPressureSensor(hass, device_id))
        sensors.append( FloTempSensor(hass, device_id))
        #sensors.append( FloPhysicalValveSensor(hass, device_id))
        sensors.append( FloDailyConsumptionSensor(hass, device_id))
        sensors.append( FloYearlyConsumptionSensor(hass, device_id))

    # create location-based sensors
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
        return ICON_FLOW_RATE

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
        return ICON_TEMP

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

    @property
    def device_class(self):
        """Return the device class for this sensor."""
        return DEVICE_CLASS_TEMPERATURE

    
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
        return ICON_PRESSURE

    def update(self):
        """Update sensor state"""
        state = self.get_telemetry('psi')
        if state:
            self.update_state( round(state, 1) )

    @property
    def unique_id(self):
        return f"flo_pressure_{self._device_id}"

    @property
    def device_class(self):
        """Return the device class for this sensor."""
        return DEVICE_CLASS_PRESSURE

class FloDailyConsumptionSensor(FloDeviceEntity):
    def __init__(self, hass, device_id):
        super().__init__(hass, f"Daily Water Consumption", device_id)
        self._unique_id = f"flo_daily_consumption_{device_id}"

    @property
    def should_poll(self):
        # FIXME: need to set appropriate scan_intervals:
        #  - daily (every 10 minutes)
        return True

    @property
    def unit_of_measurement(self):
        """gallons (g)"""
        return "gallons"

    @property
    def icon(self):
        return ICON_CONSUMPTION

    def update(self):
        # default consumption from pyflowater is daily rollup
        data = self.flo_service.consumption(self._device_id)
        if data:
            self.update_state( round(data['aggregations']['sumTotalGallonsConsumed'], 1) )

    @property
    def unique_id(self):
        return self._unique_id

class FloYearlyConsumptionSensor(FloDeviceEntity):
    def __init__(self, hass, device_id):
        super().__init__(hass, f"Yearly Water Consumption", device_id)
        self._unique_id = f"flo_yearly_consumption_{device_id}"

    @property
    def should_poll(self):
        # FIXME: need to set appropriate scan_intervals:
        #  - yearly (every day? every hour?)
        return True

    @property
    def unit_of_measurement(self):
        """gallons (g)"""
        return "gallons"

    @property
    def icon(self):
        return ICON_CONSUMPTION

    # FIXME: @Throttle
    def update(self):
        now = datetime.now()
        start_time = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)

        data = self.flo_service.consumption(self._device_id, startDate=start_time)
        if data:
            self.update_state( round(data['aggregations']['sumTotalGallonsConsumed'], 1) )

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
        return ICON_MONITORING

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
            self.set_mode
        )

    @property
    def unique_id(self):
        return f"flo_mode_{self._location_id}"
