"""Run the real Kivy map UI under Xvfb and require a downloaded tile to render."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kivy.config import Config
Config.set('graphics', 'width', '400')
Config.set('graphics', 'height', '850')
from kivy.clock import Clock
from kivy.core.window import Window
from main import PassoApp

folder = tempfile.TemporaryDirectory()
result = {'ok': False, 'error': 'Map did not finish loading'}


class SmokeApp(PassoApp):
    @property
    def user_data_dir(self):
        return folder.name

    def on_start(self):
        Clock.schedule_interval(self.check, .5)
        Clock.schedule_once(self.expire, 35)

    def check(self, dt):
        if not self.map_loaded:
            return
        if self.mapview.width <= 0 or self.mapview.height <= 0:
            return
        # Give SDL a few frames to turn the downloaded PNG into a map texture.
        Clock.unschedule(self.check)
        Clock.schedule_once(self.finished, 2)

    def finished(self, dt):
        assert self.map_source.cache_dir == self.mapview.cache_dir
        assert Path(self.map_source.cache_dir).is_dir()
        assert list(Path(self.map_source.cache_dir).glob('*.png'))
        Window.screenshot(name='mapa-validado.png')
        result['ok'] = True
        self.stop()

    def expire(self, dt):
        if not result['ok']:
            result['error'] = self.map_error or result['error']
            self.stop()


SmokeApp().run()
if not result['ok']:
    raise SystemExit(result['error'])
print('Kivy UI: HTTPS map tile downloaded, cached and rendered; screenshot saved.')
