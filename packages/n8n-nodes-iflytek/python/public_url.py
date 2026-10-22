"""Validate URLs handed to an upstream fetcher; never download user content here."""
import ipaddress
import socket
from urllib.parse import urlsplit


def public_url(value):
    if (not isinstance(value, str) or not value or len(value) > 2048
            or any(ord(char) <= 32 or ord(char) == 127 for char in value) or '\\' in value):
        raise ValueError('Invalid public URL')
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (parsed.scheme not in ('http', 'https') or not host or parsed.username is not None
                or parsed.password is not None or parsed.fragment or '%' in host
                or parsed.port not in (None, 80, 443)):
            raise ValueError('Invalid public URL')
        host = host.rstrip('.').encode('idna').decode('ascii').lower()
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            raise ValueError('Invalid public host')
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80),
                                       type=socket.SOCK_STREAM)
        ips = [ipaddress.ip_address(address[4][0]) for address in addresses]
        if not ips or any(not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified for ip in ips):
            raise ValueError('Public addresses required')
    except (ValueError, UnicodeError, OSError) as error:
        raise ValueError('Invalid public URL') from error
    # The provider performs the later fetch. DNS rebinding and its redirects still
    # require provider-side controls and an administrator-approved content host.
    return value
