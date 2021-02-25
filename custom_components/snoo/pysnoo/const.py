"""The snoo constants."""

BASE_ENDPOINT = "https://snoo-api.happiestbaby.com"
LOGIN_URI = "/us/v2/login"
REFRESH_URI = "/us/v2/refresh"
DEVICES_URI = "/me/devices"
ACCOUNT_URI = "/us/me"
BABY_URI = "/us/v3/me/baby"
SESSION_URI = "/analytics/sessions/last"
SESSION_STATS_DAILY_URI = "/ss/v2/babies/{baby_id}/sessions/aggregated/daily"
SESSION_STATS_AVG_URI = "/ss/v2/babies/{baby_id}/sessions/aggregated/avg"
DEVICE_CONFIGS_URI = "/ds/devices/{serial_number}/configs"
WAIT_TIMEOUT = 60
MANUFACTURER = "Happiestbaby"
