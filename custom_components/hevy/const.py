"""Constants for Hevy integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "hevy"
ATTRIBUTION = "Data provided by Hevy"
CONF_API_KEY = "api_key"
CONF_NAME = "name"
BASE_URL = "https://api.hevyapp.com/v1"

DEFAULT_WORKOUTS_COUNT = 10
DEFAULT_SCAN_INTERVAL = 60  # minutes

CONF_SCAN_INTERVAL = "scan_interval"
CONF_WORKOUTS_COUNT = "workouts_count"

MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 1440  # 24h
MIN_WORKOUTS_COUNT = 1
MAX_WORKOUTS_COUNT = 10  # Hevy API hard cap

EVENT_WORKOUT_COMPLETED = "hevy_workout_completed"
EVENT_WORKOUT_DELETED = "hevy_workout_deleted"
