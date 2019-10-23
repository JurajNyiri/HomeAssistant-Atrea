# HomeAssistant-Atrea
Custom component - climate platform - for Atrea ventilation units for Home Assistant

## Installation:
Copy file custom_components/atrea/climate.py to custom_components/atrea/climate.py

## Usage:
Add to configuration.yaml:

```
climate:
  - platform: atrea
    host: [IP ADDRESS TO ATREA UNIT]
    password: [PASSWORD TO ATREA UNIT]
```

Optionally, you can specify list of fan modes and list of presets by adding following to config:
```
    customize:
      fan_modes:
        - '50%'
        - '70%'
        - '100%'
      presets:
        - 'Off'
        - 'Ventilation'
        - 'Circulation'
        - 'Night precooling'
```

Complete possible list of fan modes: 

- integers between 12% - 100%

and presets: 

- "Off", "Automat", "Ventilation", "Circulation and Ventilation", "Circulation", "Night precooling", "Disbalance", "Overpressure"

## Installation using HACS
HACS is a community store for Home Assistant. You can install [HACS](https://github.com/custom-components/hacs) and then install Atrea from the HACS store.

## Track Updates
This custom component can be tracked with the help of [custom-lovelace](https://github.com/ciotlosm/custom-lovelace).

In your configuration.yaml

```
custom_updater:
  component_urls:
    - https://raw.githubusercontent.com/JurajNyiri/HomeAssistant-Atrea/master/custom_updater.json
```