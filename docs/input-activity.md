# Input activity and recovery

D1–D4 are generic controller inputs. Their names, pulse/maintained behavior,
priorities, modes and durations belong to the unit configuration. This integration
never assumes that a particular input is a kitchen, bathroom or push button.

## Normal activity

The **Forced operating mode** sensor reports the source selected by the controller
(H10712). Its input names use an HA input-entity name override first, a controller
label second, and `D1 input`…`D4 input` otherwise. Rename an input entity in HA to
personalize its source label and recovered entries. No YAML mapping is required.
The binary input sensors continue to report the contact registers, independently.

A short pulse can be missed while its timed action remains visible for minutes.
A masked request can become effective after a higher-priority source ends.
Neither observation proves the exact time of a physical press.

## Recovery without a second normal entry

Every 30 seconds the integration reads the controller's retained H10712 log.
It matches logged episodes against the source transitions seen by normal status
polling. Controller log timestamps can trail live status; matching allows one
status interval of lag and consumes each observed transition only once. If normal
polling saw the transition, **no recovery entry is added**.
An unseen episode is recovered only after it ends, with two status-poll intervals
of settling time for an in-flight update. Current episodes are left pending.

Example recovery message (using the input entity's name):

> Recovered forced-source activity at 2026-10-21 08:05:00 (unit time)

The Activity timestamp is discovery time; the message preserves the unit's time.
Backdated HA events can disappear from an already-open Activity stream.

## Persistence and limits

- The first installation baselines the existing log rather than replaying activity
  that may already exist in HA. Earlier experimental cursors migrate in place.
- Cursors and observed transitions survive normal reloads/restarts. Available
  retained days are recovered after downtime in bounded batches. Expired history
  is not recoverable. An episode spanning midnight is not a new activation.
- Contact on/off, effective mode and fan changes remain separate real state
  changes. Recovery adds no synthetic contact states and sends no commands.
- Repeated presses with no source change are not recoverable. Source resumption
  is not called a new press. Names and behavior are independent of input numbers.
- Controller and HA local clocks must agree for transition matching. Backwards
  clock changes with ambiguous episode boundaries are skipped conservatively.
- Unsupported logs and request failures do not affect normal status polling.
  Rewritten/truncated history before the cursor is not replayed; a warning is logged.
- HA event recording and cursor storage are not one transaction. A hard crash
  during the small persistence window can still duplicate the last event.

## Validation journey

1. Pulse or hold any configured input: its ordinary forced-source change appears,
   with no additional recovery entry after history polling or after it ends.
2. A whole source episode missed between status polls is recovered once after it
   ends. Automated tests simulate this without controlling a real unit.
3. Reload: consumed history and observed transitions are not replayed.
4. Rename an input: subsequent source labels and recovery entries use that name.

Verified against an R-5 RK5 log format; other controllers may lack retained logs.
