# HomeAssistant-Atrea
Custom component - sensor - for Atrea ventilation units for Home Assistant

## Usage:
Add to configuration.yaml:

```
sensor:
  - platform: atrea
    host: [IP ADDRESS TO ATREA UNIT]
    password: [PASSWORD TO ATREA UNIT]
    monitored_conditions:
      - warnings
      - alerts
      - status
```