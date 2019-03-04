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