"""
Support for Flo Water Control System inflow control device valve on/off
"""
import logging
import voluptuous as vol
from datetime import timedelta

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from homeassistant.const import ATTR_ENTITY_ID, ICON_VALVE_OPEN, ICON_VALVE_CLOSED

from . import (
    FloDeviceEntity,
    FLO_DOMAIN,
    FLO_SERVICE,
    CONF_LOCATION_ID
)

LOG = logging.getLogger(__name__)

# default to 1 minute, don't DDoS Flo servers
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string
})

SERVICE_RUN_HEALTH_TEST = 'run_health_test'
SERVICE_RUN_HEALTH_TEST_SCHEMA = { vol.Required(ATTR_ENTITY_ID): cv.time_period }
SERVICE_RUN_HEALTH_TEST_SIGNAL = f"{SERVICE_RUN_HEALTH_TEST}_%s"

STATE_OPEN = 'Open'
STATE_CLOSED = 'Closed'

# pylint: disable=unused-argument
def setup_platform(hass, config, add_switches_callback, discovery_info=None):
    """Setup the Flo Water Control System integration."""

    flo = hass.data[FLO_SERVICE]
    if flo == None or not flo.is_connected:
        LOG.warning("No connection to Flo service, ignoring platform setup")
        return False

    if discovery_info:
        location_id = discovery_info[CONF_LOCATION_ID]
    else:  # manual config
        location_id = config[CONF_LOCATION_ID]

    location = flo.location(location_id)
    if not location:
        LOG.warning(f"Flo location {location_id} not found, ignoring creation of Flo control valves")
        return False

    # iterate all devices and create a valve switch for each device
    switches = []
    for device in location['devices']:
        valve = FloWaterValve(hass, device['id'])
        switches.append(valve)

    add_switches_callback(switches)
            
    # register any exposed services
    # NOTE: would have used async_register_entity_service if this platform setup was async

    def run_health_test_handler(call):
        entity_id = call.data[ATTR_ENTITY_ID]
        async_dispatcher_send(hass, SERVICE_RUN_HEALTH_TEST_SIGNAL.format(entity_id))
    hass.services.register(FLO_DOMAIN, SERVICE_RUN_HEALTH_TEST, run_health_test_handler, SERVICE_RUN_HEALTH_TEST_SCHEMA)

class FloWaterValve(FloDeviceEntity, ToggleEntity):
    """Flo switch to turn on/off water flow."""

    def __init__(self, hass, device_id):
        super().__init__(hass, 'Water Valve', device_id)

        state = self.device_state
        if state:
            self.update()
 
    @property
    def icon(self):
        if self.state == STATE_OPEN:
            return ICON_VALVE_OPEN
        elif self.state == STATE_CLOSED:
            return ICON_VALVE_CLOSED
        else:
            return ICON_VALVE_OPEN

    @property
    def is_on(self):
        """Return true if Flo control valve TARGET is set to open (even if valve has not closed entirely yet)."""
        valve = self.device_state.get('valve')
        if valve:
            # if target is set to turn on, then return True that the device is on (even if last known is not on)
            target = valve.get('target')
            if target:
                if target == 'open':
                    return True
                else:
                    return False

            # if missing target, fallback to the last known state
            lastKnown = valve.get('lastKnown')
            if lastKnown:
                if lastKnown == 'open':
                    return True
                else:
                    return False

            return None

    def turn_on(self):
        self.flo_service.open_valve(self._device_id)

         # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be on (eventually)
        self.update_state(STATE_OPEN)

        # trigger update coordinator to read latest state from service
        self.schedule_update_ha_state(force_refresh=True)

    def turn_off(self):
        self.flo_service.close_valve(self._device_id)

        # Flo device's valve adjustments are NOT instanenous, so update state to indiciate that it WILL be off (eventually)
        self.update_state(STATE_CLOSED)

        # trigger update coordinator to read latest state from service
        self.schedule_update_ha_state(force_refresh=True)

    def run_health_test(self):
        """Run a health test."""
        self.flo_service.run_health_test(self._device_id)

    async def async_added_to_hass(self):
        """Run when entity is about to be added to hass."""
        super().async_added_to_hass()

        # register the trigger to handle run_health_test service call
        async_dispatcher_connect(
            self._hass,
            SERVICE_RUN_HEALTH_TEST_SIGNAL.format(self.entity_id),
            self.run_health_test
        )

    def update_attributes(self):
        """Update various attributes about the valve"""
        valve = self.device_state.get('valve')
        if valve:
            self._attrs['valve'] = valve
            LOG.debug(f"WOW: {self.device_state}")
            #self._attrs['nickname'] = self.device_state.get['nickname']

            #fwProperties = self.device_state.get('fwProperties')
            #if fwProperties:
            #    self._attrs['valve_actuation_count'] = fwProperties.get('valve_actuation_count')

            #healthTest = self.device_state.get('healthTest')
            #if healthTest:
            #    self._attrs['healthTest'] = healthTest.get('config')

            #self._attrs['lastHeardFromTime'] = self.device_state.get('lastHeardFromTime')

    def update(self):
        if not self.device_state:
            return

        valve = self.device_state.get('valve')
        if valve:
            target = valve.get('target')
            lastKnown = valve.get('lastKnown')

            self.update_attributes()

            # determine if the valve is open or closed
            is_open = None
            if lastKnown:
                is_open = lastKnown == 'open'
            elif target:
                is_open = target == 'open'

            if is_open == True:
                self.update_state(STATE_OPEN)
            elif is_open == False:
                self.update_state(STATE_CLOSED)
            else:
                self.update_state(None)

    @property
    def unique_id(self):
        return f"flo_valve_{self._device_id}"
