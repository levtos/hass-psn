"""Constants for the psn integration."""

from datetime import timedelta

DOMAIN = "playstation_network"
DEVICE_SCAN_INTERVAL = timedelta(seconds=30)
PSN_COORDINATOR = "psn_coordinator"
PSN_API = "psn_api"
PSN_USER = "psn_user"
CONF_EXPOSE_ATTRIBUTES_AS_ENTITIES = "attributes_as_entities"
CONF_POWER_SENSOR = "power_sensor"
CONF_REST_MODE_THRESHOLD = "rest_mode_threshold"
DEFAULT_REST_MODE_THRESHOLD = 10.0
POWER_SENSOR_DEBOUNCE_SECONDS = 5
