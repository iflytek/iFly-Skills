"""Offline public-URL checks; no DNS or HTTP traffic."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('public_url', Path(sys.argv.pop()) / 'bridge/public_url.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicURLs(unittest.TestCase):
    def test_safe_url_is_preserved(self):
        with patch.object(module.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]):
            value = 'https://example.com/file.pdf?signature=test'
            self.assertEqual(module.public_url(value), value)

    def test_private_mixed_and_special_addresses_are_rejected(self):
        for address in ['127.0.0.1', '10.1.2.3', '192.168.1.1', '169.254.169.254', '100.64.0.1',
                        '0.0.0.0', '::1', 'fc00::1', 'fe80::1', '::ffff:127.0.0.1',
                        '224.0.0.1', '240.0.0.1', 'ff02::1']:
            with self.subTest(address=address), patch.object(module.socket, 'getaddrinfo', return_value=[
                    (2, 1, 6, '', ('8.8.8.8', 443)), (2, 1, 6, '', (address, 443))]):
                with self.assertRaises(ValueError):
                    module.public_url('https://example.com/a')

    def test_malformed_credentials_and_private_hostnames_are_rejected_before_dns(self):
        with patch.object(module.socket, 'getaddrinfo', side_effect=AssertionError('Unexpected DNS')):
            for value in ['file:///etc/passwd', 'http://localhost/a', 'http://service.internal/a',
                          'http://localhost./a', 'http://a.local/a', 'https://u:p@example.com/a',
                          'https://example.com:8080/a', 'https://example.com/a#fragment',
                          'https://example.com\\@127.0.0.1/a', ' https://example.com/a',
                          'https://example.com/\n', 'http://[fe80::1%25eth0]/', 'https://example.com:bad/a']:
                with self.subTest(url=value), self.assertRaises(ValueError):
                    module.public_url(value)

    def test_dns_failure_fails_closed(self):
        for outcome in [[], OSError('private diagnostic')]:
            with patch.object(module.socket, 'getaddrinfo', side_effect=outcome if isinstance(outcome, Exception) else None,
                              return_value=outcome):
                with self.assertRaises(ValueError):
                    module.public_url('https://example.com/a')


if __name__ == '__main__':
    unittest.main()
