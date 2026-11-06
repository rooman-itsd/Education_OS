from .jitsi import JitsiProvider
from .teams import TeamsProvider
from .webex import WebexProvider
from .zoom import ZoomProvider

PROVIDERS = {"zoom": ZoomProvider, "teams": TeamsProvider, "webex": WebexProvider, "jitsi": JitsiProvider}
