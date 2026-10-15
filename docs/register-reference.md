# RD5 register notes

Source: [RD5 Modbus register reference, 2018-09-03](https://downloads.vodnici.net/uploads/wpforo/attachments/390/1937-RD5parametersCZ.pdf).
This older RD5 reference does not establish complete R-5 RK5 compatibility.

| Registers | Interpretation | PDF page |
| --- | --- | --- |
| H10205 / H10206 | Bypass opening / closing output pulses; finite values 0–32768 are milliseconds | 3 |
| H10700–H10703 | Separate program controls for power, operating mode, temperature, and zone | 1 |

The bypass table gives a maximum of 65534 but prints 65634 for continuously-on.
That is inconsistent with a 16-bit register. The integration therefore converts
only the documented finite range and preserves other valid register values in
`raw_value`; it does not guess the special-code interpretation or manufacture a
large duration. Missing/invalid readings are unavailable; valid special codes
have an unknown finite duration. This avoids contaminating duration statistics.

The library uses the unit's HTTP register interface, not a new Modbus transport.
Model/firmware-specific behavior still needs device evidence.
