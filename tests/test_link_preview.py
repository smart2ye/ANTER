import socket
import unittest
from unittest.mock import patch

from app.utils.helpers import _is_safe_preview_url, extract_link_metadata


class FakeResponse:
    status_code = 200
    headers = {'Content-Type': 'text/html; charset=utf-8'}
    is_redirect = False
    is_permanent_redirect = False

    def iter_content(self, chunk_size=16384):
        yield '''<html><head>
        <meta property="og:title" content="عنوان تجريبي">
        <meta property="og:description" content="وصف تجريبي للرابط">
        <meta property="og:image" content="https://example.com/preview.jpg">
        </head><body></body></html>'''.encode('utf-8')

    def close(self):
        pass


def public_dns(host, port, type=None):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', port))]


class LinkPreviewTests(unittest.TestCase):
    def test_private_hosts_are_rejected(self):
        self.assertFalse(_is_safe_preview_url('http://127.0.0.1:5000/secret'))
        self.assertFalse(_is_safe_preview_url('http://localhost/secret'))

    @patch('app.utils.helpers.socket.getaddrinfo', side_effect=public_dns)
    @patch('requests.Session.get', return_value=FakeResponse())
    def test_open_graph_metadata_is_extracted(self, mocked_get, mocked_dns):
        metadata = extract_link_metadata('شاهد الرابط https://example.com/article')
        self.assertEqual(metadata, (
            'https://example.com/article',
            'عنوان تجريبي',
            'وصف تجريبي للرابط',
            'https://example.com/preview.jpg',
        ))
        mocked_get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
