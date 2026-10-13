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

Requested/effective operating mode, forced operating mode, program, and season
are exposed as native status sensors. Heat-pump heating and cooling have binary
sensors. Entities are created only when their registers are present on the unit.

Optional diagnostic sensors are disabled by default: TU1/TU2/TEb/control-panel
temperatures, M1/M2/SA2/SC output voltages, requested/effective power codes, and
bypass opening/closing pulse durations. Enable the sensors you need from the device page.
Physical temperature names avoid assuming the unit's installation orientation.
Raw power codes have no percentage unit. Bypass pulses use milliseconds; special
codes have an unknown finite duration and remain available as `raw_value`
attributes. Measurement sensors do not generate device Activity entries.
Existing bypass entity unique IDs are retained; templates needing the original
code must use the `raw_value` attribute instead of the sensor state. Optional
bypass sensors remain disabled by default. See [register notes](docs/register-reference.md).

Rename entities for rooms in your own Home Assistant entity settings. Room names,
CO2 voltage calibration, and installation-specific airflow interpretations belong
in the installation configuration rather than in this integration.


On a confirmed Power_2Z device, requested/effective power diagnostics use named
fan-setting states (for example, `Norm-Circ/Min-Vent`).
Choices are read from the unit's own GUI metadata. Numeric codes remain in
`raw_value`, and entity unique IDs are preserved. Unknown codes remain unknown
with their raw value retained; units without confirmed metadata retain the raw
representation. This display feature requires pyatrea's `getPowerModeOptions()`
API; the integration falls back when that API is unavailable.

Digital-input and IN1/IN2 voltage sensor names use device labels as defaults.
Rename them in Home Assistant for preferred wording or translations; registry
name overrides take precedence. Public fixtures use generic room labels only.

Forced input states reuse the input entity's Home Assistant name override, then
its decoded device label, with IN1/IN2/D1–D4 retained in parentheses. Renaming an
input entity ID does not break this lookup: it uses the stable unique ID.
Missing labels fall back to the input identifier. Enum options follow the same
resolver as the state. Raw forced-mode codes remain in `raw_value`; historical
Activity entries keep the wording originally recorded.
