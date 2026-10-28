# Asterisk Queue Monitor for Home Assistant

A Home Assistant custom integration that reads queue status from Asterisk Manager Interface (AMI) and exposes queue and agent metrics as sensors.

## Status

Initial development version. Test against your Asterisk version and queue strategy before relying on it for operational monitoring.

## Features

- Total waiting calls and structured caller details
- Available-agent count (unpaused members with AMI member status `1`, not in a call)
- Queue and position for each waiting caller
- Wait duration, caller ID/name, and channel metadata
- Abandoned-call counter
- Configurable snapshot refresh interval (1–120 seconds)
- AMI reconnection on the next refresh after a connection loss

## Installation

1. Copy `custom_components/asterisk_queue_monitor` into the Home Assistant `custom_components` directory, or install through HACS after the repository is configured as an integration repository.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for **Asterisk Queue Monitor**.
4. Enter the AMI host, port (normally `5038`), username, and secret.

Create a dedicated AMI account with the minimum permissions needed to log in and read queue status/events. Restrict AMI access to the Home Assistant host using the Asterisk manager configuration and network firewall. Do not expose AMI directly to the public internet.

## Entities

The integration creates these sensors (entity IDs may be adjusted by Home Assistant):

- `sensor.asterisk_queue_monitor_waiting_calls` — total callers waiting; attributes include per-queue counts and a `callers` list.
- `sensor.asterisk_queue_monitor_available_agents` — eligible available agents; attributes include member status and paused-agent count.
- `sensor.asterisk_queue_monitor_waiting_callers` — caller-list sensor with structured `callers` attributes.
- `sensor.asterisk_queue_monitor_abandoned_calls` — diagnostic counter for abandoned calls.

Each caller object includes `queue`, `position`, `caller_id`, `caller_name`, `channel`, `unique_id`, and `wait_seconds`.

## Notes

- Asterisk's `QueueStatus` action is used as the authoritative snapshot. Polling defaults to every **1 second** and can be changed in integration options to any whole number from 1 to 120 seconds. Every poll requests a full queue snapshot; on large deployments, increase the interval if AMI or Home Assistant load becomes noticeable.
- Available-agent semantics can vary by queue strategy and device state. This initial implementation treats status `1` as available and excludes paused/in-call members. Validate this against your queue configuration.
- The abandoned counter is in-memory and resets when the integration reloads or Home Assistant restarts in this initial release.
- Treat caller IDs as sensitive data; limit access to dashboards and entity history as appropriate.

## Development

Contributions and bug reports are welcome. Include Home Assistant version, Asterisk version, queue strategy, and sanitized logs when reporting issues.
