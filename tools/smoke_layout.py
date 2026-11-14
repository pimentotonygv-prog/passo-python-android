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
            Window.screenshot(name='tela-erro.png')
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

    def scroll_edge(self, value):
        # Stop swipe inertia before positioning the viewport for measurement.
        effect = self.page_scroll.effect_y
        effect.velocity = 0
        effect.trigger_velocity_update.cancel()
        self.page_scroll.scroll_y = value

    def checks(self):
        for width, height in [(280, 480), (320, 568), (360, 640), (400, 850), (640, 360)]:
            Window.size = (width, height)
            self.active_home()
            yield .5
            self.assert_content()
            assert self.content.height > self.page_scroll.height
            self.scroll_edge(1)
            yield .15
            Window.screenshot(name=f'tela-{width}x{height}-inicio.png')
            # Use the page gutter: the reference layout now shows the map first.
            x = self.page_scroll.x+dp(3)
            y = self.page_scroll.center_y
            yield from self.swipe(x, y)
            assert self.page_scroll.scroll_y < .99, ('page did not scroll', width, height)
            self.scroll_edge(self.page_scroll.scroll_y)
            self.page_scroll.scroll_to(self.actions, padding=0, animate=False)
            yield .25
            x, y = self.actions.to_window(*self.actions.center)
            assert self.page_scroll.y <= y <= self.page_scroll.top, ('start inaccessible', width, height, y)
            Window.screenshot(name=f'tela-{width}x{height}-fim.png')
            # Map gestures must move the embedded map without scrolling the page.
            self.scroll_edge(self.page_scroll.scroll_y)
            self.page_scroll.scroll_to(self.mapview, padding=0, animate=False)
            yield .25
            x, y = self.mapview.to_window(*self.mapview.center)
            mx, my = self.mapview.to_window(*self.mapview.pos)
            y = (max(my, self.page_scroll.y)+min(my+self.mapview.height, self.page_scroll.top))/2
            assert my <= y <= my+self.mapview.height
            before = self.page_scroll.scroll_y
            before_camera = (self.mapview.lat, self.mapview.lon)
            yield from self.swipe(x, y, -1 if before < .5 else 1)
            assert abs(self.page_scroll.scroll_y-before) < .005, ('map moved page', width, height)
            assert sum(abs(a-b) for a,b in zip(before_camera,(self.mapview.lat,self.mapview.lon))) > .001, ('embedded map did not pan', width,height)
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

        Window.size = (400, 850)
        self.active_home()
        yield .3
        self.page_scroll.scroll_to(self.mapview, padding=0, animate=False)
        yield .3
        x, y = self.mapview.to_window(*self.mapview.center)
        before_scroll = self.page_scroll.scroll_y
        before_scale = (2**self.mapview.zoom)*self.mapview.scale
        left, right = UnitTestTouch(x-30, y), UnitTestTouch(x+30, y)
        left.touch_down()
        right.touch_down()
        yield .02
        for distance in (40, 50, 65, 80):
            left.touch_move(x-distance, y)
            right.touch_move(x+distance, y)
            yield .03
        left.touch_up()
        right.touch_up()
        yield .5
        assert (2**self.mapview.zoom)*self.mapview.scale > before_scale*1.2, 'embedded pinch did not zoom'
        assert abs(self.page_scroll.scroll_y-before_scroll) < .005, 'embedded pinch scrolled page'
        Window.screenshot(name='tela-mapa-toque-direto.png')
        self.explore_map()
        yield .3
        assert self.map_popup and self.mapview.interactive
        assert not self.follow
        farther, closer = self.popup_zoom_pair
        initial_zoom = self.mapview.zoom
        closer.trigger_action(duration=0)
        yield .3
        assert self.mapview.zoom == initial_zoom+1
        farther.trigger_action(duration=0)
        yield .3
        assert self.mapview.zoom == initial_zoom
        self.mapview.zoom = self.map_source.max_zoom
        yield .1
        self.zoom_map(1)
        assert self.mapview.zoom == self.map_source.max_zoom and closer.disabled
        self.mapview.zoom = self.map_source.min_zoom
        yield .1
        self.zoom_map(-1)
        assert self.mapview.zoom == self.map_source.min_zoom and farther.disabled

        self.mapview.zoom = 5
        self.mapview.center_on(20, 0)
        yield .3
        before_pan = (self.mapview.lat, self.mapview.lon)
        x, y = self.mapview.to_window(*self.mapview.center)
        yield from self.swipe(x, y)
        assert (abs(self.mapview.lat-before_pan[0])+abs(self.mapview.lon-before_pan[1])) > .001, 'map did not pan'
        before_lon = self.mapview.lon
        horizontal = UnitTestTouch(x, y)
        horizontal.touch_down()
        yield .02
        for distance in (20, 40, 60, 80):
            horizontal.touch_move(x+distance, y)
            yield .02
        horizontal.touch_up()
        yield .3
        assert abs(self.mapview.lon-before_lon) > .001, 'map did not pan horizontally'

        # Exercise native two-finger Scatter zoom with actual touch events.
        before_scale = (2**self.mapview.zoom)*self.mapview.scale
        x, y = self.mapview.to_window(*self.mapview.center)
        left, right = UnitTestTouch(x-30, y), UnitTestTouch(x+30, y)
        left.touch_down()
        right.touch_down()
        yield .02
        for distance in (40, 50, 65, 80):
            left.touch_move(x-distance, y)
            right.touch_move(x+distance, y)
            yield .03
        left.touch_up()
        right.touch_up()
        yield .5
        assert (2**self.mapview.zoom)*self.mapview.scale > before_scale*1.2, 'pinch did not zoom'
        zoomed_scale = (2**self.mapview.zoom)*self.mapview.scale
        left, right = UnitTestTouch(x-80, y), UnitTestTouch(x+80, y)
        left.touch_down()
        right.touch_down()
        yield .02
        for distance in (65, 50, 40, 30):
            left.touch_move(x-distance, y)
            right.touch_move(x+distance, y)
            yield .03
        left.touch_up()
        right.touch_up()
        yield .5
        assert (2**self.mapview.zoom)*self.mapview.scale < zoomed_scale*.85, 'pinch did not zoom out'
        Window.screenshot(name='tela-mapa-livre-zoom.png')

        camera = (self.mapview.lat, self.mapview.lon, self.mapview.zoom)
        self.preview_position(10, 20, 5)
        yield .2
        assert all(abs(a-b) < .000001 for a, b in zip(camera, (self.mapview.lat, self.mapview.lon, self.mapview.zoom)))

        # A recorded fix updates the route but must preserve the explored camera.
        camera = (self.mapview.lat, self.mapview.lon, self.mapview.zoom)
        self.store.checkpoint(dict(id='camera-test', date=1700000000000, mode='walk', weight=70,
            points=[dict(lat=10, lon=20, time=1700000000000, seg=1)], distance=0,
            duration=5000, status='running', accuracy=5))
        self.refresh()
        yield .2
        assert not self.follow
        assert all(abs(a-b) < .000001 for a, b in zip(camera, (self.mapview.lat, self.mapview.lon, self.mapview.zoom)))
        self.center()
        yield .2
        assert self.follow and abs(self.mapview.lat-10) < .000001 and abs(self.mapview.lon-20) < .000001
        self.store.checkpoint({})
        self.map_popup.dismiss()
        yield .3
        assert not self.map_popup and self.mapview.interactive
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
        self.scroll_edge(0)
        yield .2
        Window.screenshot(name='tela-280x480-sobre-fim.png')
        self.store.archive(dict(id='test', date=1700000000000, mode='walk', distance=1234,
                                duration=600000, kcal=46, points=[]))
        self.history()
        yield .4
        self.assert_content()
        self.scroll_edge(0)
        yield .2
        Window.screenshot(name='tela-280x480-historico-fim.png')


LayoutApp().run()
if not result['ok']:
    raise SystemExit(result['error'] or 'UI test did not complete')
print('Responsive UI and touch scrolling: passed.')
