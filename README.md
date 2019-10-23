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

Optionally you can specify list of fan modes and list of presets by adding this to config:
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

Complete possible list of fan modes: '12%', '20%', '30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%'
and presets: "Off", "Automat", "Ventilation", "Night precooling", "Disbalance"

## Installation using HACS
HACS is a community store for Home Assistant. You can instal [HACS](https://github.com/custom-components/hacs) and then install Atrea from the HACS store.

## Track Updates
This custom component can be tracked with the help of [custom-lovelace](https://github.com/ciotlosm/custom-lovelace).

In your configuration.yaml

```
custom_updater:
  component_urls:
    - https://raw.githubusercontent.com/JurajNyiri/HomeAssistant-Atrea/master/custom_updater.json
```