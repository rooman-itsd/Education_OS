from .garmin import GarminProvider
from .google_health import GoogleHealthProvider
from .polar import PolarProvider
from .strava import StravaProvider

PROVIDERS = {
    "garmin": GarminProvider,
    "polar": PolarProvider,
    "google-health": GoogleHealthProvider,
    "strava": StravaProvider,
}
