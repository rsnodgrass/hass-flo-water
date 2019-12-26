# Flo Water Control for Home Assistant

Support for [Flo Smart water monitoring and control device](https://amzn.to/2WBn8tW?tag=rynoshark-20) for Home Assistant. [Flo](https://meetflo.com) is typically installed on the main water supply line and has sensors for flow rate, pressure, and temperature as well as shut off capabilities. Water shut off can be done manually, remotely, as well as automatically by Flo's emergency monitoring service when a leak is detected.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=WREP29UDAMB6G)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

### Supported Features

- sensors: water flow rate (gpm), water pressure (psi), water temperature (&deg;F)
- switching water supply on/off
- multiple Flo devices and locations
- changing the FloSense water leak monitoring mode (home, away, sleep)

## Installation

### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [CHANGELOG](CHANGELOG.md) for what has changed in each version.

Visit the Home Assistant community if you need [help with installation and configuration of Flo](https://community.home-assistant.io/t/flo-smart-water-leak-detector/119532).

### Step 1: Install Flo Custom Components

Easiest installation is by setting up [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs), and then adding the "Integration" repository: rsnodgrass/hass-flo-water.

However you can also manually copy all the files in [flo/](https://github.com/rsnodgrass/hass-flo-water/custom_components/flo) directory to `/config/custom_components/flo` on your Home Assistant installation.

### Step 2: Configure Sensors

Example configuration:

```yaml
flo:
    username: your@email.com
    password: your_flo_password
```

### Step 3: Add Lovelace Card

The following is a simplest Lovelace card which shows data from the Flo sensors:

```yaml
type: entities
entities:
  - entity: sensor.flo_water_flow_rate
  - entity: sensor.flo_water_pressure
  - entity: sensor.flo_water_temperature
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
* [Flo by Moen](https://meetflo.com) (official product page)
* [15% OFF purchases of Flo](https://meetflo.referralrock.com/l/818758/)
* [pyflowater](https://github.com/rsnodgrass/pyflowater)

## Known Issues

* BUG: Flo accounts with multiple houses currently don't work. Only a single Flo device per account
* BUG: does not yet support the Flo v2 API

#### Feature Requests

Priority improvements:

- support metric unit system (liter, C, kPa)
- auto-create a pressure sensor for status of water flow (Ok, Warning, Critical)

Other ideas (no plans to add currently):

- support triggering the system test of a Flo device
- support leak detection sensitivity settings (all, small, bigger, biggest)
- support Flo alerts (leaks detected)
- total water usage for the day/week
- support Flo's fixtures beta feature breaking down usage by type (e.g. toilets, appliances, faucet, irrigation, etc)

## Unsupported 'master' branch status

* Currently converting over to pyflowater and the Flo V2 cloud APIs

## Automation Ideas

- automatically turn on Away mode for water control system when house goes into Away mode (and vice-a-versa)
- pre-warm heated towel rack when shower flow rate is detected
- toilet flush detection as an occupancy sensor (e.g. disable Away modes)