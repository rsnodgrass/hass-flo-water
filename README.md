# Flo by Moen Water Monitor for Home Assistant

Support for [Flo Smart water monitoring and control device](http://fbuy.me/v/rsnodgrass) for Home Assistant. [Flo](http://fbuy.me/v/rsnodgrass) is typically installed on the main water supply line and has sensors for flow rate, pressure, and temperature as well as shut off capabilities. Water shut off can be done manually, remotely, as well as automatically by Flo's emergency monitoring service when a leak is detected.

![release_badge](https://img.shields.io/github/v/release/rsnodgrass/hass-flo-water.svg)
![release_date](https://img.shields.io/github/release-date/rsnodgrass/hass-flo-water.svg)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://buymeacoffee.com/DYks67r)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=WREP29UDAMB6G)

## THIS WILL BE DEPRECATED JANUARY 1, 2021

The time has come to deprecate this integration as Home Assistant 115.0 that will be released September 17, 2020 will finally have a [native Flo by Moen integration](https://rc.home-assistant.io/integrations/flo/).

**You can still buy your [Flo by Moen](http://fbuy.me/v/rsnodgrass) device direct!**

## IMPORTANT NOTES

* **FLO DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**
* **Version 3.x is a BREAKING CHANGE** and requires specifying `email` key instead of `username` (if you manually configure through configuration.yaml)

### Features

- sensors:
    * water flow rate (gpm)
    * water pressure (psi)
    * water temperature (&deg;F)
    * water consumption (g) - daily
- services:
    * turn valve on/off
    * set monitoring mode (home, away, sleep)
    * run health test
- multiple Flo devices at single location
- multiple locations with Flo devices and ability to restrict locations (for users with multiple houses or locations)
- reduced polling of Flo webservice to avoid unintentional DDoS

## Support

Visit the Home Assistant community if you need [help with installation and configuration of Flo](https://community.home-assistant.io/t/flo-smart-water-leak-detector/119532).

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/rsnodgrass/hass-flo-water/releases).

### Step 1: Install Custom Components

Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup, then add the "Integration" repository: `rsnodgrass/hass-flo-water`.

### Step 2: Configuration

**DO NOT MANUALLY CONFIGURE SENSORS/SWITCHES, ONLY CONFIGURE USING `flo:` AS BELOW**. Configuration flow UI is being added in version 3.0 of this integration.

Example configuration:

```yaml
flo:
  email: your@email.com
  password: your_flo_password
```

The following is an advanced configuration to limit sensors to a single location (if multiple houses on a single account). The location_id can be found by turning logging to DEBUG for `pyflowater` component, or installing [`pyflowater`](https://github.com/rsnodgrass/pyflowater) and running the `example-client.py` script to show all information about your Flo devices.

```yaml
flo:
  email: your@email.com
  password: your_flo_password
  locations:
    - d6b2822a-f2ce-44b0-bbe2-3600a095d494
```

#### Alternative: Configure via UI

**THE UI CONFIGURATION IS CURRENTLY DISABLED**

Version 3.0 added the ability to configure credentials for Flo through the Home Assistant UI. Go to Configuration -> Integrations and click the + symbol to configure. Search for Flo and enter your username and password.

![Flo Lovelace Examples](https://github.com/rsnodgrass/hass-flo-water/blob/master/lovelace/Config-Flow-Add.png?raw=true)
![Flo Lovelace Examples](https://github.com/rsnodgrass/hass-flo-water/blob/master/lovelace/Config-Flow-Card.png?raw=true)


### Step 3: Add Lovelace Card

The following is a simplest Lovelace card which shows data from the Flo sensors (adjust as needed to use your own entity_id names):

```yaml
type: entities
entities:
  - entity: sensor.water_flow_rate
  - entity: sensor.water_pressure
  - entity: sensor.water_temperature
  - entity: sensor.daily_water_consumption
  - entity: sensor.flo_monitoring_mode
```

![Flo Lovelace Examples](https://github.com/rsnodgrass/hass-flo-water/blob/master/lovelace/entities.png?raw=true)

Alternative Lovelace example with gauges that turn colors when pressure or flow rate is high:

```yaml
cards:
  - type: gauge
    name: Flow
    entity: sensor.water_flow_rate
    severity:
      green: 0
      yellow: 10
      red: 12
  - type: gauge
    name: Pressure
    entity: sensor.water_pressure
    severity:
      green: 0
      yellow: 70
      red: 90
  - type: gauge
    name: Temp
    entity: sensor.water_temperature
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

* **Flo has removed the water temperature reading as of June 2020; this is no longer available (replaced by "area temp" which is not exposed through any known API at this time)**

#### Feature Requests

- support metric unit system (liter, C, kPa)
- merge turn on/off, mode, and current status into a single entity
- auto-create a pressure sensor for status of water flow (Ok, Warning, Critical)

Other ideas (no plans to add currently):

- support leak detection sensitivity settings (all, small, bigger, biggest)
- support FloSense alerts (leaks detected)
- support Flo's fixtures beta feature breaking down usage by type (e.g. toilets, appliances, faucet, irrigation, etc)
- leak detection sensitivity setting

## Automation Ideas

- automatically turn on Away mode for water control system when house goes into Away mode (and vice-a-versa)
- pre-warm heated towel rack when shower flow rate is detected
- toilet flush detection as an occupancy sensor (e.g. disable Away modes)
