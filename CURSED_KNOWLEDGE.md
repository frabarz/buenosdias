# Cursed Knowledge

Cursed knowledge we have learned building buenosdias that we wish we never knew.

## 8/15/2026

- **`ConfigEntry.add_update_listener` is cursed**

  Home Assistant's `ConfigEntry.add_update_listener` does **not** deduplicate:
  it blindly appends to `entry.update_listeners`
  (`homeassistant/config_entries.py`, `ConfigEntry.add_update_listener`).
  We called it inside `async_setup_entry`, so every reload added another copy.
  The first time a user saved a preference through the options flow
  (`config_flow.py` → `_replace_options` → `async_create_entry`), HA's
  `OptionsFlowManager.async_finish_flow` called `async_update_entry`, which
  fired *every* accumulated listener. Each one ran
  `_async_update_listener` → `async_reload`, and each reload re-added another
  duplicate — an exponential reload cascade. The event loop flooded with
  `Setup of buenosdias.sensor/switch` cycles until the websocket hit
  `Client unable to keep up with pending messages. Reached 4096 pending
  messages` and HA hard-froze while the "entry updated" events queued up.

  The rule: **always keep the unlisten callback returned by
  `add_update_listener` and call it in `async_unload_entry`**
  (see `__init__.py:async_setup_entry` / `async_unload_entry`).
  It is the same lifecycle discipline as `event.async_track_*` and
  `async_track_time_change`.

  Tell-tale symptom in the log: a single config-entry `modified_at` timestamp,
  then a wall of repeating `Setting up <platform>` lines, and a websocket
  connection dropping with 4096 pending `entry updated` messages.