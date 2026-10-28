"""Constants for the Asterisk Queue Monitor integration."""

DOMAIN = "asterisk_queue_monitor"
PLATFORMS = ["sensor"]

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_SECRET = "secret"
CONF_REFRESH_INTERVAL = "refresh_interval"

DEFAULT_PORT = 5038
DEFAULT_REFRESH_INTERVAL = 1

SENSOR_WAITING_CALLS = "waiting_calls"
SENSOR_AVAILABLE_AGENTS = "available_agents"
SENSOR_WAITING_CALLERS = "waiting_callers"
SENSOR_ABANDONED_CALLS = "abandoned_calls"

EVENT_QUEUE_CALLER_ABANDON = "QueueCallerAbandon"
EVENT_QUEUE_CALLER_JOIN = "QueueCallerJoin"
EVENT_QUEUE_CALLER_LEAVE = "QueueCallerLeave"
EVENT_QUEUE_MEMBER = "QueueMember"
EVENT_QUEUE_MEMBER_STATUS = "QueueMemberStatus"
EVENT_QUEUE_MEMBER_PAUSE = "QueueMemberPause"
EVENT_QUEUE_STATUS_COMPLETE = "QueueStatusComplete"
