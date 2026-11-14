"""Content-driven sizes and a scrolling-friendly embedded map."""
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy_garden.mapview import MapView


class FlowLabel(Label):
    min_height = NumericProperty(0)

    def __init__(self, text='', minimum=42, font=16, **kwargs):
        super().__init__(text=text, size_hint_y=None, font_size=sp(font),
                         halign='center', valign='middle', **kwargs)
        self.min_height = dp(minimum)
        self.bind(width=self.reflow, texture_size=self.fit_text, min_height=self.fit_text)
        self.reflow()

    def reflow(self, *_):
        self.text_size = (max(dp(1), self.width-dp(12)), None)

    def fit_text(self, *_):
        self.height = max(self.min_height, self.texture_size[1]+dp(12))


class FlowButton(Button):
    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=dp(48), font_size=sp(16),
                         halign='center', valign='middle', **kwargs)
        self.bind(width=self.reflow, texture_size=self.fit_text)
        self.reflow()

    def reflow(self, *_):
        self.text_size = (max(dp(1), self.width-dp(20)), None)

    def fit_text(self, *_):
        self.height = max(dp(48), self.texture_size[1]+dp(20))


class ContentRow(BoxLayout):
    """Rows grow with their tallest button/label instead of clipping it."""
    def __init__(self, **kwargs):
        super().__init__(size_hint_y=None, height=dp(48), **kwargs)

    def add_widget(self, widget, *args, **kwargs):
        super().add_widget(widget, *args, **kwargs)
        widget.bind(height=self.fit_children)
        self.fit_children()

    def remove_widget(self, widget, *args, **kwargs):
        widget.unbind(height=self.fit_children)
        super().remove_widget(widget, *args, **kwargs)
        self.fit_children()

    def fit_children(self, *_):
        self.height = max([dp(48)] + [child.height for child in self.children])


class PageMap(MapView):
    interactive = BooleanProperty(True)

    def on_touch_down(self, touch):
        if not self.interactive:
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if not self.interactive:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if not self.interactive:
            return False
        return super().on_touch_up(touch)


class MapScrollView(ScrollView):
    """Map touches go straight to its Scatter; other touches scroll the page."""
    def __init__(self, **kwargs):
        self.map_target = None
        self.map_touches = set()
        super().__init__(**kwargs)

    def on_touch_down(self, touch):
        target = self.map_target
        if target is not None and target.interactive and not target.disabled and self.collide_point(*touch.pos):
            x, y = target.to_window(*target.pos)
            in_map = x <= touch.x <= x+target.width and y <= touch.y <= y+target.height
            on_bar = touch.x >= self.right-max(dp(12), self.bar_width*2)
            if in_map and not on_bar and self.children:
                touch.push()
                try:
                    touch.apply_transform_2d(self.to_local)
                    handled = self.children[0].dispatch('on_touch_down', touch)
                finally:
                    touch.pop()
                if handled:
                    self.map_touches.add(touch.uid)
                    return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.uid in self.map_touches:
            # The map's Scatter grabbed the touch and receives its own updates.
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.uid in self.map_touches:
            self.map_touches.discard(touch.uid)
            return True
        return super().on_touch_up(touch)
