import base64
import tempfile
import unittest
from pathlib import Path
from passo.maps import TileCache, MapLoadError

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1kAAAAASUVORK5CYII=')


class Response:
    def __init__(self, content=PNG, error=None):
        self.content, self.error = content, error

    def raise_for_status(self):
        if self.error:
            raise self.error


class MapTests(unittest.TestCase):
    def test_missing_custom_cache_directory_gets_created(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)/'private'/'tiles'
            calls = []
            def get(url, **kwargs):
                calls.append((url, kwargs))
                return Response()
            cache = TileCache(folder, get=get, ca_file='trusted-certificates.pem')
            result = Path(cache.fetch('https://tile.openstreetmap.org/0/0/0.png', 'world.png'))
            self.assertEqual(result.read_bytes(), PNG)
            self.assertEqual(calls[0][1]['verify'], 'trusted-certificates.pem')
            self.assertEqual(list(folder.glob('*.tmp')), [])
            # A second view uses the existing validated image without a request.
            cache.fetch('https://tile.openstreetmap.org/0/0/0.png', 'world.png')
            self.assertEqual(len(calls), 1)

    def test_invalid_old_cache_is_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'tile.png'
            target.write_bytes(b'<html>Error</html>')
            result = TileCache(folder, get=lambda *a, **k: Response()).fetch('https://tiles/test.png', 'tile.png')
            self.assertEqual(Path(result).read_bytes(), PNG)

    def test_html_and_partial_download_are_not_cached(self):
        for content in (b'<html>Forbidden</html>', PNG[:30]):
            with tempfile.TemporaryDirectory() as folder:
                cache = TileCache(folder, get=lambda *a, **k: Response(content))
                with self.assertRaises(MapLoadError):
                    cache.fetch('https://tiles/test.png', 'tile.png')
                self.assertFalse((Path(folder)/'tile.png').exists())

    def test_network_failure_can_be_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = TileCache(folder, get=lambda *a, **k: Response(error=OSError('offline')))
            with self.assertRaises(MapLoadError):
                cache.fetch('https://tiles/test.png', 'tile.png')
            cache.get = lambda *a, **k: Response()
            self.assertEqual(Path(cache.fetch('https://tiles/test.png', 'tile.png')).read_bytes(), PNG)

    def test_plain_http_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = TileCache(folder, get=lambda *a, **k: self.fail('must not download'))
            with self.assertRaises(MapLoadError):
                cache.fetch('http://tiles/test.png', 'tile.png')
            with self.assertRaises(MapLoadError):
                cache.fetch('https://tiles/test.png', '../tile.png')
