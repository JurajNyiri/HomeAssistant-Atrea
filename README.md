# HomeAssistant-Atrea

Custom component - climate platform - for Atrea ventilation units for Home Assistant

## Installation using HACS

HACS is a community store for Home Assistant. You can install [HACS](https://github.com/custom-components/hacs) and then install Atrea from the HACS store.

## Installation:

1. In your Home Assistant instance, create directory `/custom_components/atrea` in your `/config` directory.
2. Copy all files from [/custom_components/atrea](https://github.com/JurajNyiri/HomeAssistant-Atrea/tree/master/custom_components/atrea) of this repository to the newly created directory in your Home Assistant.

## Usage:

Add climate unit via Integrations (search for Atrea) in Home Assistant UI. You can also simply click the button below if you have MyHomeAssistant redirects set up.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=atrea)

Active warnings and alerts are exposed as button entities on the Atrea device.
Each button includes the condition's parameter code, severity, and translated
message. The button becomes unavailable when the condition clears. The filter
replacement warning can be acknowledged from its button. Alert buttons use the
unit's global alarm reset command, matching the original web UI. Other warning
buttons report that their condition cannot be acknowledged because the web UI
does not provide an acknowledgement action for them.

IN1 and IN2 are exposed as voltage sensors and SA1 as a percentage sensor. The
input voltages can be converted to measurements such as CO2 concentration
according to the scaling specified by the connected 0–10 V sensor.

The integration also exposes airflow requirements and measurements, and
heat-pump defrost state when their registers are available. Airflow values are
only meaningful in constant-flow operation; ODA airflow applies to supported
R5 units.

Outdoor, averaged outdoor, supply, extract, exhaust, and indoor air
temperatures are available as native sensors. D1–D4 inputs are exposed as
binary sensors.

### Control: Manual or Weekly

The **Control** select changes the unit's program only:

- **Manual**: use manual setpoints, including changes from Home Assistant.
- **Weekly**: let the unit's weekly schedule supply its setpoints.

It has no Off choice and does not change operating mode, fan setting, or target
temperature. Off in the operating-mode or fan controls is a separate setting.
The existing climate auto/fan_only/off API remains for compatibility; its
fan_only action also requests Ventilation, so use Control to change only the
program. Creating the Control entity does not send any unit commands.

The selector is discovered when all RD5 program channels, or all legacy RD4
program channels, are present. It reports Manual/Weekly only when all agree.
Temporary, mixed, or invalid channel states appear as unknown, with the reason
and raw channel values in attributes. Temporary is not a selectable option,
matching the inspected RD5 GUI. A command is reported successful only after a
fresh readback confirms the requested program; failures produce an HA error.
Hardware validation targets R-5 RK5; RD4 behavior has automated coverage only.
