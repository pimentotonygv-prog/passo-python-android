"""MapView source with a shared explicit cache directory and visible load state."""
import os
from kivy_garden.mapview.source import MapSource
from kivy_garden.mapview.downloader import Downloader
from passo.maps import TileCache, MapLoadError


class ReliableMapSource(MapSource):
    def __init__(self, folder, on_status, ca_file):
        self.tile_cache = TileCache(folder, ca_file=ca_file)
        self.on_status = on_status
        super().__init__(url='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                         cache_dir=str(folder), cache_key='passo-osm-https',
                         attribution='© OpenStreetMap contributors')

    def fill_tile(self, tile):
        if tile.state != 'done':
            Downloader.instance(cache_dir=self.cache_dir).submit(self.load_tile, tile)

    def load_tile(self, tile):
        if tile.state == 'done':
            return None
        y = self.get_row_count(tile.zoom)-tile.tile_y-1
        url = self.url.format(z=tile.zoom, x=tile.tile_x, y=y)
        try:
            path = self.tile_cache.fetch(url, os.path.basename(tile.cache_fn))
            return self.loaded, (tile, path)
        except MapLoadError as exc:
            return self.failed, (tile, str(exc))

    def loaded(self, tile, path):
        # Downloader executes returned callbacks on Kivy's UI thread.
        if tile.state != 'done':
            tile.set_source(path)
            self.on_status(True, '')

    def failed(self, tile, message):
        if tile.state != 'done':
            self.on_status(False, message)
