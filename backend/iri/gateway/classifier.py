"""Decide whether a resolved model endpoint is inside or outside the trust boundary.

Everything downstream keys off this answer, so the failure mode must be
over-redaction, never under-redaction: anything not positively identified as
this host is treated as remote, and unparseable input returns UNKNOWN, which
callers handle exactly as OUTSIDE_BOUNDARY.

Do NOT simplify this into a substring test. The host is taken from a real URL
parse precisely because these forms are remote and read as local otherwise:

    localhost.evil.com                  -- a hostname containing "localhost"
    http://user@localhost:1@evil.com/   -- userinfo that looks like a host
    http://evil.com/?target=localhost   -- the string appears in the query

A private address (10.x, 192.168.x, 172.16-31.x, 169.254.x) is another machine,
not this one, and is OUTSIDE_BOUNDARY. Only loopback counts as inside.
"""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit

from iri.gateway.types import DestinationClass


def classify_endpoint(endpoint: str) -> DestinationClass:
    # Step 1: Check if endpoint is empty or only whitespace
    if not endpoint.strip():
        return DestinationClass.UNKNOWN

    # Step 2: Prepend "http://" if no scheme is present
    if "://" not in endpoint:
        endpoint = "http://" + endpoint

    # Step 3: Parse the URL and extract the hostname
    try:
        parsed_url = urlsplit(endpoint)
        hostname = parsed_url.hostname
    except Exception:
        return DestinationClass.UNKNOWN

    # Step 4: Normalise: lowercase, then strip any trailing "."
    if hostname is None:
        return DestinationClass.UNKNOWN
    host = hostname.lower().rstrip('.')

    # Step 5: If the normalised host == "localhost" -> return INSIDE_BOUNDARY
    if host == "localhost":
        return DestinationClass.INSIDE_BOUNDARY

    # Step 6: Try `ip_address(host)`
    try:
        ip = ip_address(host)
        if ip.is_loopback:
            return DestinationClass.INSIDE_BOUNDARY
        else:
            return DestinationClass.OUTSIDE_BOUNDARY
    except ValueError:
        # If it raises ValueError, the host is a normal DNS name
        return DestinationClass.OUTSIDE_BOUNDARY
