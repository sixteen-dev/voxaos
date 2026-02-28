---
name: home-assistant
description: Control and monitor smart home devices via Home Assistant. Use when the
  user asks to turn on/off lights, check sensor readings, set thermostat temperature,
  get home status, control any smart device, or analyze home sensor data patterns.
  Also handles daily/weekly home briefings and insights.
---

## Home Assistant Control & Insights

You have access to a Home Assistant instance with connected smart home devices
(Zigbee sensors, lights, switches, climate, plugs, presence sensors, IR blasters).

### Reading State
- Use ha_get_states(domain) to list devices by type
- Use ha_get_state(entity_id) to check a specific device
- Common domains: light, switch, sensor, climate, binary_sensor, media_player

### Controlling Devices
- Use ha_call_service to trigger physical device actions:
  - Lights: ha_call_service("light", "turn_on", "light.living_room", {"brightness": 200})
  - AC/Climate: ha_call_service("climate", "set_temperature", "climate.bedroom_ac", {"temperature": 22})
  - Switches: ha_call_service("switch", "turn_off", "switch.kitchen_plug")
  - Media: ha_call_service("media_player", "media_play_pause", "media_player.tv")
- Use ha_set_state to update entity state directly via POST /api/states/<entity_id>

### Analyzing Sensor Data
When asked for insights, briefings, or "what happened at home":
1. Pull history with ha_get_history for relevant sensors (last 24h default)
2. Look for: temperature anomalies, presence patterns, power spikes, devices left on
3. Summarize conversationally — lead with unusual or actionable findings
4. Keep voice response under 30 seconds

### Safety
- Always confirm before controlling climate (AC, heating) — changing temp costs money
- Never turn off devices that sound safety-critical (alarms, cameras, medical)
- For batch operations ("turn off everything"), list what will be affected first
