"""Exercise responsive layouts with real touch input in a Kivy/Xvfb window."""
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kivy.config import Config
Config.set('graphics', 'width', '320')
Config.set('graphics', 'height', '568')
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.tests.common import UnitTestTouch
from passo.responsive import FlowLabel, FlowButton
from main import PassoApp

folder = tempfile.TemporaryDirectory()
result = {'ok': False, 'error': ''}


class LayoutApp(PassoApp):
    @property
    def user_data_dir(self):
        return folder.name

    def on_start(self):
        self.steps = self.checks()
        Clock.schedule_once(self.advance, .3)

    def advance(self, dt):
        try:
            delay = next(self.steps)
        except StopIteration:
            result['ok'] = True
            self.stop()
        except Exception:
            result['error'] = traceback.format_exc()
            self.stop()
        else:
            Clock.schedule_once(self.advance, delay)

    def assert_content(self):
        assert self.content.width <= self.page_scroll.width+1
        assert self.content.height >= self.content.minimum_height-1
        for widget in self.content.walk():
            if isinstance(widget, (FlowLabel, FlowButton)):
                assert widget.height+1 >= widget.texture_size[1], (widget.text, widget.size, widget.texture_size)
                assert widget.text_size[0] <= widget.width, widget.text
        siblings = sorted(self.content.children, key=lambda child: child.y)
        for lower, upper in zip(siblings, siblings[1:]):
            assert lower.top <= upper.y+1, ('overlap', lower, upper)

    def swipe(self, x, y, direction=1):
        touch = UnitTestTouch(x, y)
        touch.touch_down()
        yield .02
        for distance in (20, 40, 60, 80):
            touch.touch_move(x, y+direction*dp(distance))
            yield .02
        touch.touch_up()
        yield .3

    def checks(self):
        for width, height in [(280, 480), (320, 568), (360, 640), (400, 850), (640, 360)]:
            Window.size = (width, height)
            self.active_home()
            yield .5
            self.assert_content()
            assert self.content.height > self.page_scroll.height
            self.page_scroll.scroll_y = 1
            yield .15
            Window.screenshot(name=f'tela-{width}x{height}-inicio.png')
            yield from self.swipe(self.page_scroll.center_x, self.page_scroll.center_y)
            assert self.page_scroll.scroll_y < .99, ('page did not scroll', width, height)
            self.page_scroll.scroll_y = 0
            yield .25
            x, y = self.actions.to_window(*self.actions.center)
            assert self.page_scroll.y <= y <= self.page_scroll.top, ('start inaccessible', width, height, y)
            Window.screenshot(name=f'tela-{width}x{height}-fim.png')
            # Finger gestures over the embedded map must scroll the page too.
            self.page_scroll.scroll_to(self.mapview, padding=0, animate=False)
            yield .25
            x, y = self.mapview.to_window(*self.mapview.center)
            y = max(self.page_scroll.y+dp(90), min(self.page_scroll.top-dp(90), y))
            before = self.page_scroll.scroll_y
            yield from self.swipe(x, y, -1 if before < .5 else 1)
            assert abs(self.page_scroll.scroll_y-before) > .005, ('map blocked page scroll', width, height)
            # Repeated metric updates must not replace a button during a tap.
            button = self.actions.children[0]
            self.refresh()
            assert self.actions.children[0] is button
            open_height = self.mapbox.height
            self.toggle_map()
            yield .2
            assert self.mapbox.height == 0
            self.toggle_map()
            yield .2
            assert self.mapbox.height >= open_height-1
            print(f'Responsive {width}x{height}: text fits, swipes scroll, last action reachable, map collapses.')

        self.explore_map()
        yield .3
        assert self.map_popup and self.mapview.interactive
        self.map_popup.dismiss()
        yield .3
        assert not self.map_popup and not self.mapview.interactive
        assert self.mapview.parent is self.map_frame

        Window.size = (280, 480)
        self.active_home()
        self.store.set('service_error', 'Ative a localização precisa e confira as permissões do celular. '*6)
        self.refresh()
        yield .4
        assert self.status.height >= self.status.texture_size[1]
        assert self.status.height > dp(50)
        self.store.set('service_error', '')
        self.about()
        yield .4
        self.assert_content()
        self.page_scroll.scroll_y = 0
        yield .2
        Window.screenshot(name='tela-280x480-sobre-fim.png')
        self.store.archive(dict(id='test', date=1700000000000, mode='walk', distance=1234,
                                duration=600000, kcal=46, points=[]))
        self.history()
        yield .4
        self.assert_content()
        self.page_scroll.scroll_y = 0
        yield .2
        Window.screenshot(name='tela-280x480-historico-fim.png')


LayoutApp().run()
if not result['ok']:
    raise SystemExit(result['error'] or 'UI test did not complete')
print('Responsive UI and touch scrolling: passed.')
