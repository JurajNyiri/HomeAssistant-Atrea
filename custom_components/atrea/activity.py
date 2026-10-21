"""Recover forced-input activity from the controller's retained H10712 log."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import date, datetime, timedelta
from typing import Any

import requests
from homeassistant.const import CONF_IP_ADDRESS, EVENT_LOGBOOK_ENTRY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, LOGGER, MIN_TIME_BETWEEN_SCANS

LOG_REGISTER = "H10712"
INPUT_REGISTERS = {f"D{i + 1}": f"D1020{i}" for i in range(4)}
POLL_INTERVAL = timedelta(seconds=30)
MAX_DAYS_PER_POLL = 3


def parse_samples(value: str) -> list[tuple[int, int]]:
    """Preserve log order, including same-second changes and clock adjustments."""
    samples = []
    for item in value.split(";"):
        if not item:
            continue
        seconds, raw = item.split(",", maxsplit=1)
        sample = int(seconds), int(raw)
        if not 0 <= sample[0] < 86400:
            raise ValueError("Invalid time in Atrea log")
        samples.append(sample)
    return samples


def input_for_mode(value: int, supported: dict[int, Any]) -> str | None:
    mode = supported.get(value)
    name = getattr(mode, "name", "").upper()
    return name if name in INPUT_REGISTERS else None


def fetch_log(atrea: Any, day: date | None) -> Any:
    """Read log dates or one day's samples using the existing controller session."""
    query = "type=0" if day is None else f"type=1&date={day:%Y%m%d}"
    response = requests.get(atrea.getURL(f"config/log.cgi?{query}"), timeout=15)
    response.raise_for_status()
    if day is None:
        return sorted(
            {
                datetime.strptime(line.strip(), "%Y%m%d").date()
                for line in response.text.splitlines()
                if line.strip()
            }
        )
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get(LOG_REGISTER), str):
        raise ValueError("H10712 is not available in the controller log")
    return parse_samples(payload[LOG_REGISTER])


def _entity_id(hass: HomeAssistant, ip: str, register: str) -> str | None:
    unique_id = slugify(f"{slugify(f'atrea_{ip}')}_{register}")
    return er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, unique_id)


def input_label(hass, entry, data, input_name, entity_id=None):
    """HA rename, then controller label, then generic input identifier."""
    entity_id = entity_id or _entity_id(
        hass, entry.data.get(CONF_IP_ADDRESS, ""), INPUT_REGISTERS[input_name]
    )
    registered = er.async_get(hass).async_get(entity_id) if entity_id else None
    if registered and registered.name:
        return registered.name
    label = ((data.get("userLabels") or {}).get(input_name) or "").strip()
    return (
        f"{label} ({input_name})"
        if label and label.strip() != input_name
        else f"{input_name} input"
    )


class ActivityLog:
    """Track retained transitions; never change input states or send commands."""

    def __init__(self, hass: HomeAssistant, entry: Any, atrea: Any, data: dict) -> None:
        self.hass, self.entry, self.atrea, self.data = hass, entry, atrea, data
        self.store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_activity")
        self.cursor: dict = {}
        self.observation_store = Store(
            hass, 1, f"{DOMAIN}_{entry.entry_id}_activity_observations"
        )
        self.observations: list[list] = []
        self._last_source: int | None = None
        self._unsub_status = None
        self._task: asyncio.Task | None = None
        self._unsub = None
        self._stopped = False
        self._lock = asyncio.Lock()

    async def async_start(self) -> None:
        self.cursor = await self.store.async_load() or {}
        observed = await self.observation_store.async_load() or {}
        self.observations = observed.get("transitions", [])
        self._last_source = observed.get("last_source")
        self._unsub_status = self.data["coordinator"].async_add_listener(
            self._observe_status
        )
        self._observe_status()
        self._unsub = async_track_time_interval(
            self.hass, self._schedule, POLL_INTERVAL
        )
        self._schedule()

    @callback
    def _observe_status(self) -> None:
        """Remember successful status samples already presented by the source sensor."""
        if self._stopped or not self.data["coordinator"].last_update_success:
            return
        stamp = self.data.get("status_observed_at")
        raw = (self.data.get("status") or {}).get(LOG_REGISTER)
        if stamp is None or raw is None:
            return
        ip = self.entry.data.get(CONF_IP_ADDRESS, "")
        registry = er.async_get(self.hass)
        source_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{slugify(f'atrea_{ip}')}_forced_operating_mode"
        )
        source = registry.async_get(source_id) if source_id else None
        if source is None or source.disabled_by is not None:
            return
        try:
            point = [stamp, int(raw)]
        except (TypeError, ValueError):
            return
        if point[1] == self._last_source:
            return
        self._last_source = point[1]
        if input_for_mode(point[1], dict(self.data.get("supportedForcedModes") or [])):
            self.observations.append(point)
        self.observation_store.async_delay_save(self._observation_data, 1)

    @callback
    def _observation_data(self):
        return {"last_source": self._last_source, "transitions": self.observations}

    def _observed_transition(self, value: int, start: str, end: str | None):
        # Retained logging can trail live status (six seconds on the tested RK5).
        # Allow one status interval, and consume each observation only once.
        earliest = (datetime.fromisoformat(start) - MIN_TIME_BETWEEN_SCANS).isoformat()
        return next(
            (
                point
                for point in self.observations
                if point[1] == value
                and earliest <= point[0]
                and (end is None or point[0] < end)
            ),
            None,
        )

    @callback
    def _schedule(self, _now=None) -> None:
        if not self._stopped and (self._task is None or self._task.done()):
            self._task = self.hass.async_create_task(self.async_poll())

    async def async_stop(self) -> None:
        self._stopped = True
        if self._unsub_status:
            self._unsub_status()
            self._unsub_status = None
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        await self.observation_store.async_save(self._observation_data())

    async def async_poll(self) -> None:
        async with self._lock:
            if self._stopped:
                return
            try:
                await self._poll()
            except (requests.RequestException, ValueError, TypeError):
                # Unsupported controllers and transient/auth failures are retried;
                # neither can advance the cursor or affect normal status polling.
                LOGGER.debug("Unable to read Atrea input history", exc_info=True)

    async def _poll(self) -> None:
        timezone = (
            dt_util.get_time_zone(self.hass.config.time_zone)
            or dt_util.DEFAULT_TIME_ZONE
        )
        now = dt_util.now(timezone)
        today = now.date()
        saved_day = date.fromisoformat(self.cursor["date"]) if self.cursor else today
        days = [today]
        if saved_day < today:
            available = await self.hass.async_add_executor_job(
                fetch_log, self.atrea, None
            )
            days = sorted(
                {day for day in available if saved_day <= day <= today} | {today}
            )
        supported = dict(self.data.get("supportedForcedModes") or [])
        if not supported:
            return
        for day in days[:MAX_DAYS_PER_POLL]:
            samples = await self.hass.async_add_executor_job(fetch_log, self.atrea, day)
            if self._stopped or not samples:
                return
            same_day = self.cursor.get("date") == day.isoformat()
            start = 0
            if same_day and "position" in self.cursor:
                start = self.cursor["position"]
                # A rewritten/truncated log cannot be safely replayed. Retry until
                # it matches rather than inventing duplicate activations.
                if start > len(samples) or (
                    start and list(samples[start - 1]) != self.cursor["sample"]
                ):
                    LOGGER.warning(
                        "Atrea history changed before its saved cursor for %s", day
                    )
                    return
            elif same_day:
                # Migrate the earlier seconds-only cursor without replaying it.
                while start < len(samples) and samples[start][0] <= self.cursor.get(
                    "seconds", -1
                ):
                    start += 1
            elif not self.cursor:
                # Baseline first installation: previous HA activity is unknown.
                start = len(samples)
            previous = samples[start - 1][1] if start else None
            for index in range(start, len(samples)):
                seconds, value = samples[index]
                input_name = input_for_mode(value, supported)
                # The first midnight row is a snapshot, not an input activation.
                if (
                    input_name
                    and value != previous
                    and not (index == 0 and seconds == 0)
                ):
                    when = datetime.combine(day, datetime.min.time()) + timedelta(
                        seconds=seconds
                    )
                    start_time = when.isoformat()
                    end_time = await self._episode_end(day, samples, index, today)
                    observed = self._observed_transition(value, start_time, end_time)
                    if observed is not None:
                        # Commit consumption before looking at another episode,
                        # so one live transition cannot hide two retained ones.
                        await self._save(day, index + 1, samples[index])
                        if observed in self.observations:
                            self.observations.remove(observed)
                        previous = value
                        continue
                    if end_time is None or (
                        datetime.fromisoformat(end_time) + 2 * MIN_TIME_BETWEEN_SCANS
                        > now.replace(tzinfo=None)
                    ):
                        # Give normal polling the whole episode to see it. An
                        # active episode must never race history into a duplicate.
                        if index:
                            await self._save(day, index, samples[index - 1])
                        return
                    if end_time <= start_time:
                        # A backwards controller clock makes matching ambiguous.
                        previous = value
                        continue
                    entity_id = _entity_id(
                        self.hass,
                        self.entry.data.get(CONF_IP_ADDRESS, ""),
                        INPUT_REGISTERS[input_name],
                    )
                    if entity_id is None:
                        # Save earlier rows, but retry this one after discovery.
                        if index:
                            await self._save(day, index, samples[index - 1])
                        return
                    name = input_label(
                        self.hass, self.entry, self.data, input_name, entity_id
                    )
                    self.hass.bus.async_fire(
                        EVENT_LOGBOOK_ENTRY,
                        {
                            "name": name or f"{input_name} input",
                            "message": f"Recovered forced-source activity at {when:%Y-%m-%d %H:%M:%S} (unit time)",
                            "entity_id": entity_id,
                        },
                    )
                previous = value
            await self._save(day, len(samples), samples[-1])

    async def _episode_end(self, day, samples, index, today) -> str | None:
        """Find a real source change, including an episode spanning midnight."""
        value = samples[index][1]
        remaining = samples[index + 1 :]
        for _ in range(MAX_DAYS_PER_POLL):
            for seconds, raw in remaining:
                if raw != value:
                    return (
                        datetime.combine(day, datetime.min.time())
                        + timedelta(seconds=seconds)
                    ).isoformat()
            if day >= today:
                return None
            day += timedelta(days=1)
            remaining = await self.hass.async_add_executor_job(
                fetch_log, self.atrea, day
            )
        return None

    async def _save(self, day: date, position: int, sample: tuple[int, int]) -> None:
        cursor = {"date": day.isoformat(), "position": position, "sample": list(sample)}
        if cursor != self.cursor:
            await self.store.async_save(cursor)
            self.cursor = cursor
            cutoff = (
                datetime.combine(day, datetime.min.time())
                + timedelta(seconds=sample[0])
            ).isoformat()
            self.observations = [
                point for point in self.observations if point[0] >= cutoff
            ]
            self.observation_store.async_delay_save(self._observation_data, 1)
