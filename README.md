# HomeAssistant-Atrea
Custom component - climate platform - for Atrea ventilation units for Home Assistant

## Installation:
Copy file climate.py to custom_components/atrea/climate.py

## Usage:
Add to configuration.yaml:

```
climate:
  - platform: atrea
    host: [IP ADDRESS TO ATREA UNIT]
    password: [PASSWORD TO ATREA UNIT]
```

## Track Updates
This custom component can be tracked with the help of [custom-lovelace](https://github.com/ciotlosm/custom-lovelace).

In your configuration.yaml

```
custom_updater:
  component_urls:
    - https://raw.githubusercontent.com/JurajNyiri/HomeAssistant-Atrea/master/custom_updater.json
```