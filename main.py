"""Kivy Android application; launch on desktop only for a UI preview."""
import time
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Ellipse
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy_garden.mapview import MapView, MapLayer
from kivy_garden.mapview.source import MapSource
from kivy_garden.mapview import downloader

from passo.android_bridge import AndroidBridge
from passo.core import to_gpx
from passo.storage import Store

GREEN = (.14, .44, .30, 1)
INK = (.06, .18, .15, 1)
downloader.USER_AGENT = 'PassoPython/2.0 (Android walking tracker; Kivy MapView)'


def clock(ms):
    s = int(ms/1000)
    return f'{s//3600:02}:{s//60%60:02}:{s%60:02}'


class RouteLayer(MapLayer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []

    def reposition(self):
        if not self.parent:
            return
        view = self.parent
        self.canvas.clear()
        groups = []
        for point in self.points:
            if not groups or groups[-1][0] != point.get('seg', 0):
                groups.append((point.get('seg', 0), []))
            groups[-1][1].extend(view.get_window_xy_from(point['lat'], point['lon'], view.zoom))
        with self.canvas:
            Color(*GREEN)
            for _, coordinates in groups:
                if len(coordinates) >= 4:
                    Line(points=coordinates, width=dp(2))
            if self.points:
                p = self.points[-1]
                x, y = view.get_window_xy_from(p['lat'], p['lon'], view.zoom)
                Ellipse(pos=(x-dp(5), y-dp(5)), size=(dp(10), dp(10)))


class PassoApp(App):
    title = 'Passo Python'

    def button(self, text, action):
        return Button(text=text, size_hint_y=None, height=dp(48), background_normal='',
                      background_color=GREEN, color=(1, 1, 1, 1),
                      on_release=lambda *_: action())

    def label(self, text, height=42, font=16):
        label = Label(text=text, color=INK, font_size=font, size_hint_y=None, height=dp(height),
                      halign='center', valign='middle')
        label.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))
        return label

    def build(self):
        Window.clearcolor = (.96, .97, .95, 1)
        self.store = Store(self.user_data_dir)
        self.bridge = AndroidBridge(self.user_data_dir, self.message)
        self.mode, self.viewing = 'walk', None
        self.signature, self.follow = None, True
        self.root_box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(12))
        self.root_box.add_widget(self.label('passo.  |  Python para Android', 45, 23))
        nav = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        nav.add_widget(self.button('Atividade', self.active_home))
        nav.add_widget(self.button('Histórico', self.history))
        nav.add_widget(self.button('Sobre', self.about))
        self.root_box.add_widget(nav)
        self.body = BoxLayout(orientation='vertical', spacing=dp(7))
        self.root_box.add_widget(self.body)
        self.mapview = MapView(zoom=2, lat=0, lon=0,
                               map_source=MapSource(url='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                                                    attribution='© OpenStreetMap contributors'),
                               cache_dir=str(Path(self.user_data_dir)/'tiles'))
        self.route = RouteLayer()
        self.mapview.add_layer(self.route, mode='window')
        self.mapview.bind(on_touch_down=self.map_touched)
        self.home()
        Clock.schedule_interval(self.refresh, 1)
        return self.root_box

    def message(self, text):
        popup = Popup(title='Passo', size_hint=(.92, .48), content=self.label(str(text), 120))
        popup.open()

    def confirm(self, text, callback):
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        box.add_widget(self.label(text, 90))
        popup = Popup(title='Confirmar', content=box, size_hint=(.92, .55))
        box.add_widget(self.button('Confirmar', lambda: (popup.dismiss(), callback())))
        box.add_widget(self.button('Cancelar', popup.dismiss))
        popup.open()

    def scroll_content(self):
        self.body.clear_widgets()
        scroll = ScrollView()
        box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        box.bind(minimum_height=box.setter('height'))
        scroll.add_widget(box)
        self.body.add_widget(scroll)
        return box

    def home(self):
        self.page = 'home'
        # Detach the map before disposing the old layout.
        if self.mapview.parent:
            self.mapview.parent.remove_widget(self.mapview)
        self.body.clear_widgets()
        self.setup = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(104), spacing=dp(5))
        modes = BoxLayout(spacing=dp(5))
        self.walk = self.button('Caminhada', lambda: self.choose('walk'))
        self.run = self.button('Corrida', lambda: self.choose('run'))
        modes.add_widget(self.walk)
        modes.add_widget(self.run)
        self.setup.add_widget(modes)
        weightrow = BoxLayout(size_hint_y=None, height=dp(45))
        weightrow.add_widget(self.label('Seu peso (kg)', 45))
        self.weight = TextInput(text=str(self.store.get('weight', 70)), multiline=False, input_type='number')
        weightrow.add_widget(self.weight)
        self.setup.add_widget(weightrow)
        self.body.add_widget(self.setup)
        self.stats = self.label('', 76, 19)
        self.status = self.label('', 50, 14)
        self.body.add_widget(self.stats)
        self.body.add_widget(self.status)
        self.toggle = self.button('', self.toggle_map)
        self.body.add_widget(self.toggle)
        self.mapbox = BoxLayout(orientation='vertical', spacing=dp(4))
        self.mapbox.add_widget(self.mapview)
        self.mapbox.add_widget(self.button('Centralizar GPS', self.center))
        self.body.add_widget(self.mapbox)
        self.actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.body.add_widget(self.actions)
        self.apply_map()
        self.choose(self.mode)
        self.refresh()

    def active_home(self):
        self.viewing = None
        self.signature = None
        self.home()

    def choose(self, mode):
        self.mode = mode
        self.walk.background_color = GREEN if mode == 'walk' else (.38, .48, .40, 1)
        self.run.background_color = GREEN if mode == 'run' else (.38, .48, .40, 1)

    def toggle_map(self):
        self.store.set('map_open', not self.store.get('map_open', True))
        self.apply_map()

    def apply_map(self):
        opened = self.store.get('map_open', True)
        self.toggle.text = 'Fechar mapa GPS' if opened else 'Abrir mapa GPS'
        self.mapbox.opacity = 1 if opened else 0
        self.mapbox.disabled = not opened
        self.mapbox.size_hint_y = 1 if opened else None
        if not opened:
            self.mapbox.height = 0
        else:
            Clock.schedule_once(lambda dt: self.route.reposition(), .1)

    def map_touched(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self.follow = False

    def center(self):
        self.follow = True
        points = self.route.points
        if points:
            self.mapview.zoom = 17
            self.mapview.center_on(points[-1]['lat'], points[-1]['lon'])
        else:
            self.message('Inicie uma atividade e aguarde o sinal do GPS.')

    def send(self, action, **kwargs):
        def perform():
            # Do not queue multiple starts while the Python service boots.
            if time.time()-self.store.get('last_command', 0) < 2:
                return
            self.store.set('last_command', time.time())
            self.store.command(action, **kwargs)
            if not self.store.get('active') or time.time()-self.store.get('heartbeat', 0) > 5:
                self.bridge.launch()
            self.viewing = None
            Clock.schedule_once(self.refresh, 1)
        if action in ('start', 'resume'):
            self.bridge.ready(perform)
        else:
            # A recovered activity also needs a service to pause/finish.
            from kivy.utils import platform
            if platform == 'android':
                perform()

    def start(self):
        try:
            weight = float(self.weight.text.replace(',', '.'))
            if not 20 <= weight <= 300:
                raise ValueError()
        except ValueError:
            self.message('Informe um peso entre 20 e 300 kg.')
            return
        self.store.set('weight', weight)
        self.follow = True
        self.send('start', mode=self.mode, weight=weight)

    def refresh(self, *_):
        if getattr(self, 'page', '') != 'home':
            return
        active = self.store.get('active', {})
        a = self.viewing or active
        duration, distance = a.get('duration', 0), a.get('distance', 0)
        pace = duration/distance if distance >= 50 else None
        pace_text = f'{int(pace)//60}:{int(pace)%60:02}' if pace is not None else '--'
        self.stats.text = (f'{clock(duration)}    |    {distance/1000:.2f} km\n'
                           f'{a.get("kcal", 0):.0f} kcal    |    {pace_text} min/km\n'
                           f'{distance/duration*3600 if duration else 0:.1f} km/h')
        interrupted = bool(active) and time.time()-self.store.get('heartbeat', 0) > 5
        error = self.store.get('service_error', '') or a.get('error', '')
        if self.viewing:
            status = 'Atividade salva'
        elif error:
            status = error
        elif interrupted:
            status = 'Registro interrompido. Retome ou finalize.'
        elif a.get('status') == 'running':
            status = (f'GPS: precisão estimada de {a.get("accuracy", 0):.0f} m'
                      if time.time()*1000-a.get('lastFix', 0) < 10000 else 'Aguardando sinal GPS preciso...')
        else:
            status = 'Atividade pausada' if active else 'Pronto para começar'
        self.status.text = status
        self.setup.disabled = bool(active or self.viewing)
        self.setup.opacity = 0 if active or self.viewing else 1
        self.setup.height = 0 if active or self.viewing else dp(104)
        self.actions.clear_widgets()
        if self.viewing:
            self.actions.add_widget(self.button('Voltar ao histórico', self.history))
        elif active:
            running = a.get('status') == 'running' and not interrupted
            self.actions.add_widget(self.button('Pausar' if running else 'Retomar',
                                                lambda: self.send('pause' if running else 'resume')))
            self.actions.add_widget(self.button('Parar e salvar', lambda: self.confirm(
                'Encerrar o GPS e salvar a atividade?', lambda: self.send('finish'))))
        else:
            self.actions.add_widget(self.button('Iniciar', self.start))
        signature = (a.get('id'), len(a.get('points', [])))
        if self.signature != signature:
            self.signature = signature
            self.route.points = a.get('points', [])
            self.route.reposition()
            if self.route.points and self.follow:
                self.center()

    def history(self):
        self.page = 'history'
        box = self.scroll_content()
        records = self.store.history()
        if not records:
            box.add_widget(self.label('Suas atividades salvas aparecerão aqui.', 80))
        for a in records:
            title = 'Corrida' if a['mode'] == 'run' else 'Caminhada'
            date = datetime.fromtimestamp(a['date']/1000).strftime('%d/%m/%Y %H:%M')
            box.add_widget(self.label(f'{title} · {date}\n{a["distance"]/1000:.2f} km · {clock(a["duration"])}', 70))
            box.add_widget(self.button('Ver percurso', lambda a=a: self.view(a)))
            box.add_widget(self.button('Exportar GPX', lambda a=a: self.export(a)))
            box.add_widget(self.button('Apagar', lambda a=a: self.confirm('Apagar esta atividade?',
                           lambda: (self.store.delete(a['id']), self.history()))))

    def view(self, activity):
        self.viewing = activity
        self.signature = None
        self.store.set('map_open', True)
        self.follow = True
        self.home()
        points = activity.get('points', [])
        if points:
            self.mapview.zoom = 15
            self.mapview.center_on(sum(p['lat'] for p in points)/len(points),
                                   sum(p['lon'] for p in points)/len(points))

    def export(self, activity):
        try:
            self.bridge.export(activity['id'], to_gpx(activity))
        except ValueError as exc:
            self.message(str(exc))

    def about(self):
        self.page = 'about'
        box = self.scroll_content()
        paragraphs = [
            ('Como usar', 'Escolha caminhada ou corrida, informe seu peso e inicie. Permita localização precisa e aguarde o GPS ao ar livre antes de sair.'),
            ('Mapa GPS', 'Abrir ou fechar o mapa não pausa a gravação. Use Pausar nas paradas e Parar e salvar ao terminar. Arraste o mapa para explorar e toque em Centralizar GPS para acompanhar.'),
            ('Precisão', 'Pontos com incerteza acima de 15 m são descartados. Intervalos maiores que 8 segundos ficam separados. A linha usa pontos medidos, sem ajuste automático às ruas. Prédios e árvores podem causar desvios.'),
            ('Tela apagada', 'O Android usa um serviço com notificação para gravar. Alguns celulares restringem tarefas por economia de bateria. É necessário testar no aparelho.'),
            ('Calorias estimadas', 'Estimativa por peso e tempo: caminhada 3,8 MET; corrida 7,5 MET. Não é uma medição direta. O ritmo depende da distância registrada.'),
            ('Privacidade', 'Percursos e peso ficam no celular. O mapa usa internet e solicita imagens ao OpenStreetMap, que recebe seu IP e a área visualizada. O GPS funciona sem internet. Exporte GPX antes de desinstalar.'),
            ('Versão Python', 'Projeto independente do Passo original. O histórico do outro aplicativo não é importado automaticamente. Código e compilação Android ainda precisam de validação no celular.')]
        for title, body in paragraphs:
            box.add_widget(self.label(title, 36, 20))
            box.add_widget(self.label(body, 130, 15))
        box.add_widget(self.button('Voltar à atividade', lambda: (setattr(self, 'viewing', None), self.home())))

    def on_pause(self):
        return True

    def on_resume(self):
        self.refresh()


if __name__ == '__main__':
    PassoApp().run()
