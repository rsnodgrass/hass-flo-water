# Flo Water Control for Home Assistant

Support for [Flo Smart water monitoring and control device](https://amzn.to/2WBn8tW?tag=rynoshark-20) for Home Assistant. [Flo](https://meetflo.com) is typically installed on the main water supply line and has sensors for flow rate, pressure, and temperature as well as shut off capabilities. Water shut off can be done manually, remotely, as well as automatically by Flo's emergency monitoring service when a leak is detected.

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

- sensors: water flow rate (gpm), water pressure (psi), water temperature (&deg;F), water consumption (g)
- multiple Flo devices and locations

#### Not Supported

- switching water supply on/off
- changing the FloSense water leak monitoring mode (home, away, sleep)

## Installation

#### Versions

The 'master' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/rsnodgrass/hass-flo-water/releases).

### Step 1: Install Flo Custom Components

Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup, then add the "Integration" repository: rsnodgrass/hass-flo-water.

Note: Manual installation by direct download and copying is not supported, if you have issues, please first try installing this integration with HACS.

### Step 2: Configure Sensors

Example configuration:

```yaml
flo:
    username: your@email.com
    password: your_flo_password
    startdate: 2020-01-01
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
* [Flo by Moen](https://meetflo.com) (official product page)
* [15% OFF purchases of Flo](https://l.facebook.com/l.php?u=http%3A%2F%2Ffbuy.me%2Fo7V9I%3Ffbm%3D16505%26fbclid%3DIwAR15JOQdK5VYZpQqKkmFcMrWIKDe8XyR4ecrEYU2ZWiBzT08GwSxVCzq7sA&h=AT1QzphEpsIm7u4bgH8j1mtOifoyCHenHjndQvsD1D2d7o3FD8Xni24PYC59NA3lhKrZGHUWA6R2BIdzvqCM_Zt5x6kgmKxeBI36p5W0gAgi4bKaYj6kjgRMTxpARYJEJaGpvzw&__tn__=H-R&c[0]=AT33dWStfMtxxLDbsvLiMQ7_USqTAwNn1AZpODVitM-88PyL-dNPwrBGjc-taRETr07nikaNpoOlmPclmak0KlONJjlG3z-ijZJRVZEE1Vhzkrkij_XXCGsTzRnwA_57qIJAiRsQCZmviPXt865_Zpv-VkNGu3tv3h9yMZL_tncm8w1Z)
* [pyflowater](https://github.com/rsnodgrass/pyflowater)

## Known Issues

* BUG: Flo accounts with multiple houses currently don't work. Only a single Flo device per account
* BUG: does not yet support the Flo v2 API

#### Feature Requests

- support metric unit system (liter, C, kPa)
- auto-create a pressure sensor for status of water flow (Ok, Warning, Critical)

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
