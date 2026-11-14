"""Light, rounded visual components shared by all Passo screens."""
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from passo.responsive import FlowButton

BLUE = (.20, .25, 1, 1)
INK = (.09, .11, .18, 1)
MUTED = (.43, .46, .55, 1)
PALE = (.93, .94, 1, 1)

class SoftButton(FlowButton):
    fill = ListProperty(BLUE)

    def __init__(self, **kwargs):
        kwargs.pop('background_color', None)
        kwargs.pop('background_normal', None)
        super().__init__(background_normal='', background_down='',
                         background_color=(0, 0, 0, 0), **kwargs)
        with self.canvas.before:
            self.paint = Color(*self.fill)
            self.shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self.redraw, size=self.redraw, fill=self.redraw,
                  state=self.redraw, disabled=self.redraw)

    def redraw(self, *_):
        shade = .82 if self.state == 'down' else 1
        r, g, b, a = self.fill
        self.paint.rgba = (r*shade, g*shade, b*shade, .35 if self.disabled else a)
        self.shape.pos, self.shape.size = self.pos, self.size

class Card(BoxLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('spacing', dp(6))
        kwargs.setdefault('padding', dp(14))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(.89, .90, .95, .45)
            self.shadow = RoundedRectangle(radius=[dp(23)])
            Color(1, 1, 1, 1)
            self.surface = RoundedRectangle(radius=[dp(22)])
        self.bind(pos=self.redraw, size=self.redraw, minimum_height=self.setter('height'))

    def redraw(self, *_):
        self.surface.pos, self.surface.size = self.pos, self.size
        self.shadow.pos = (self.x, self.y-dp(3))
        self.shadow.size = self.size
