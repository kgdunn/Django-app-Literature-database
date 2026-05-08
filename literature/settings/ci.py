"""CI settings: prod-like (Postgres, DEBUG=False) but test-client friendly.

Imports prod, then disables the HTTPS-only middleware behaviour that would
otherwise 301-redirect every Django test client request, since the test
client speaks plain HTTP. Also extends ALLOWED_HOSTS with `testserver`
(the host name Django's test client uses by default) so calls like
`Client().get("/")` don't trip `DisallowedHost`. Used by
.github/workflows/ci.yml so pytest runs against the same database engine
production uses.
"""

from .prod import *  # noqa: F401,F403
from .prod import ALLOWED_HOSTS

ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ["testserver"]

SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
