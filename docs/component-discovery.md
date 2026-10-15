# Component discovery rules

Source: RD5 device GUI `lang/pars.xml`, `lang/content_2.xml` and `Service.js`,
checked against an R-5 RK5 on 2026-10-15. These rules use configuration already
returned by `getStatus`; no additional requests or installer access are needed.

| Telemetry | Configuration |
| --- | --- |
| SA1 H10202 | H10504 preheater: 0 absent, 1 electric, 2 liquid |
| Bypass H10205/H10206 | H11800: 0 absent |
| SC H10204 | C10509=1 (R4/5 circulation) or H11700 circulation damper not explicitly absent |
| SA2 H10203 | Omit only when both primary H10503 and secondary H10517 heaters are explicitly absent |
| C10215 demand | Primary H10503: 5 heat pump or 6 combined heater; 0..4 do not use this demand output |
| C10216 demand | H10507: 0 absent, 1 water, 2 DX/heat pump |
| D10207 defrost | Omit when primary type is 0..4 and cooling type is 0 or 1 |
| I11600..I11605 airflow | H10510=1 standard constant flow; H10510=4 with C10509=1 Power_2Z constant flow |
| I11604/I11605 outdoor airflow | Additionally omit when C10509=0 |

Unknown component enums and missing configuration preserve existing discovery.
Airflow requires a recognized control mode, as before. The circulation percentage
still requires Power_2Z because its scaling has been validated there.

The GUI component list confirms that C10216 also belongs to water coolers.
Its legacy heat-pump display name is retained in this change; naming and actuator
interpretation are separate from discovery. No new TA2, pressure, alarm or runtime
sensors are added here. Temperature error/sentinel conversion remains unchanged.

Configuration may change without a register disappearing. Apply the same rules
to discovery and entity availability; do not delete entity registry entries.
