# Flo Water Monitoring & Control for Home Assistant

Support for [Flo Smart water monitoring and control device](http://fbuy.me/v/rsnodgrass) for Home Assistant. [Flo](http://fbuy.me/v/rsnodgrass) is typically installed on the main water supply line and has sensors for flow rate, pressure, and temperature as well as shut off capabilities. Water shut off can be done manually, remotely, as well as automatically by Flo's emergency monitoring service when a leak is detected.

**NOTE: FLO DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**

![beta_badge](https://img.shields.io/badge/maturity-Beta-yellow.png)
![release_badge](https://img.shields.io/github/v/release/rsnodgrass/hass-flo-water.svg)
![release_date](https://img.shields.io/github/release-date/rsnodgrass/hass-flo-water.svg)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=WREP29UDAMB6G)

## Support

Visit the Home Assistant community if you need [help with installation and configuration of Flo](https://community.home-assistant.io/t/flo-smart-water-leak-detector/119532).

This integration was developed to cover use cases for my home integration, which I wanted to contribute back to the community. Additional features beyond what has already been provided are the responsibility of the community to implement (unless trivial to add).

### Supported Features

- sensors:
    * water flow rate (gpm)
    * water pressure (psi)
    * water temperature (&deg;F)
    * water consumption (g) - daily and yearly
- multiple Flo devices and locations
- restricting monitoring to a single location (for users with multiple houses or locations)
- careful polling of Flo webservice to avoid accidental DDoS

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/rsnodgrass/hass-flo-water/releases).

### Step 1: Install Custom Components

Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup, then add the "Integration" repository: `rsnodgrass/hass-flo-water`.

### Step 2: Configure Sensors

Example configuration:

```yaml
flo:
  username: your@email.com
  password: your_flo_password
```

Advanced configuration to limit sensors to a single location (if multiple houses on a single account). The location_id can be found by turning logging to DEBUG for `pyflowater` component, or installing [`pyflowater`](https://github.com/rsnodgrass/pyflowater) and running the `example-client.py` script to show all information about your Flo devices.

```yaml
flo:
  username: your@email.com
  password: your_flo_password
  locations:
    - d6b2822a-f2ce-44b0-bbe2-3600a095d494
```

### Step 3: Add Lovelace Card

The following is a simplest Lovelace card which shows data from the Flo sensors:

```yaml
type: entities
entities:
  - entity: sensor.flo_water_flow_rate
  - entity: sensor.flo_water_pressure
  - entity: sensor.flo_water_temperature
  - entity: sensor.flo_water_consumption
```

![Flo Lovelace Examples](https://github.com/rsnodgrass/hass-flo-water/blob/master/lovelace/entities.png?raw=true)

Alternatively, Lovelace example with gauges that turn colors when pressure or flow rate is high:

```yaml
cards:
  - type: gauge
    name: Water Pressure
    entity: sensor.flo_water_pressure
    max: 100
    severity:
      green: 0
      yellow: 70
      red: 80
  - type: gauge
    name: Flow Rate
    entity: sensor.flo_water_flow_rate
    max: 15
    severity:
      green: 0
      yellow: 10
      red: 12
  - type: gauge
    name: Temp
    entity: sensor.flo_water_temperature
    max: 75
type: horizontal-stack
```

More complex cards can be created, for example the following shows both the basic entities card as well as a card built with mini-graph-card (see flo/lovelace/ folder for example cards):

![Flo Lovelace Examples](https://github.com/rsnodgrass/hass-flo-water/blob/master/lovelace/mini-graph.png?raw=true)

## See Also

* [Community support for Home Assistant Flo sensor](https://community.home-assistant.io/t/flo-smart-water-leak-detector/119532)
* [Check price of Flo water monitoring device on Amazon.com](https://amzn.to/2WBn8tW?tag=rynoshark-20)
* [Flo by Moen](http://fbuy.me/v/rsnodgrass) (official product page)
* *[Purchase Flo and get two free Smart Water Detectors](http://fbuy.me/v/rsnodgrass)*
* [pyflowater](https://github.com/rsnodgrass/pyflowater)

## Known Issues

* Flo has removed the water temperature reading as of June 2020; this is no longer available (replaced by "area temp")

#### Feature Requests

- support metric unit system (liter, C, kPa)
- auto-create a pressure sensor for status of water flow (Ok, Warning, Critical)
- changing the FloSense water leak monitoring mode (home, away, sleep)

Other ideas (no plans to add currently):

- support triggering the system test of a Flo device
- support leak detection sensitivity settings (all, small, bigger, biggest)
- support FloSense alerts (leaks detected)
- total water usage for the day/week (can be done with combination of consumption and utility meter)
- support Flo's fixtures beta feature breaking down usage by type (e.g. toilets, appliances, faucet, irrigation, etc)

## Automation Ideas

- automatically turn on Away mode for water control system when house goes into Away mode (and vice-a-versa)
- pre-warm heated towel rack when shower flow rate is detected
- toilet flush detection as an occupancy sensor (e.g. disable Away modes)
