# FIXME: make this the future base class of a valve (well, at least the plumbing aspect of the valve)

import logging

from homeassistant.const import PRECISION_TENTHS, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import display_temp as show_temp

LOG = logging.getLogger(__name__)

ATTR_ATTRIBUTION = "attribution"
ATTR_FLOW_RATE = "flow_rate"
ATTR_PRESSURE = "pressure"
ATTR_TEMPERATURE = "temperature"

class PlumbingEntity(Entity):
    """ABC for plumbing data."""

    @property
    def temperature(self):
        """Return the plumbing temperature."""
        raise NotImplementedError()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        raise NotImplementedError()

    @property
    def pressure(self):
        """Return the pressure (aka head)."""
        return None

    @property
    def flow_rate(self): # m3/s or ft3/s
        """Return the flow rate."""
        return None

    @property
    def flow_velocity(self): # m/s or ft/s
        """Return the flow velocity."""
        return None

    @property
    def attribution(self):
        """Return the attribution."""
        return None

    @property
    def precision(self):
        """Return the precision of the temperature value."""
        return (
            PRECISION_TENTHS
            if self.temperature_unit == TEMP_CELSIUS
            else PRECISION_WHOLE
        )

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}
        if self.temperature is not None:
            data[ATTR_TEMPERATURE] = show_temp(
                self.hass, self.temperature, self.temperature_unit, self.precision
            )

        pressure = self.pressure
        if pressure is not None:
            data[ATTR_PRESSURE] = pressure

        attribution = self.attribution
        if attribution is not None:
            data[ATTR_ATTRIBUTION] = attribution

        return data

    @property
    def state(self):
        """Return the current state."""
        return self.condition

    @property
    def condition(self):
        """Return the current condition."""
        raise NotImplementedError()
