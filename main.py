"""Kivy Android application; launch on desktop only for a UI preview."""
import time
import os
import certifi
from datetime import datetime
from pathlib import Path

# Configure trusted certificates before the map/network libraries are imported.
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.effects.scroll import ScrollEffect
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

from passo.theme import SoftButton, Card, BLUE, MUTED, PALE
from passo.android_bridge import AndroidBridge
from passo.core import to_gpx
from passo.storage import Store
from passo.map_widget import ReliableMapSource
from passo.responsive import FlowLabel, FlowButton, ContentRow, PageMap, MapScrollView

GREEN = BLUE
INK = (.09, .11, .18, 1)
downloader.USER_AGENT = 'PassoPython/2.0 (Android walking tracker; Kivy MapView)'


def clock(ms):
    s = int(ms/1000)
    return f'{s//3600:02}:{s//60%60:02}:{s%60:02}'


class RouteLayer(MapLayer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []
        self.preview_fix = None

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
            if self.points or self.preview_fix:
                p = self.points[-1] if self.points else self.preview_fix
                x, y = view.get_window_xy_from(p['lat'], p['lon'], view.zoom)
                Ellipse(pos=(x-dp(5), y-dp(5)), size=(dp(10), dp(10)))


class PassoApp(App):
    title = 'passo'

    def button(self, text, action):
        primary = text in ('Iniciar atividade', 'Pausar', 'Retomar', 'Parar e salvar', 'Confirmar')
        return SoftButton(text=text, fill=BLUE if primary else PALE,
                      color=(1, 1, 1, 1) if primary else BLUE,
                      on_release=lambda *_: action())

    def label(self, text, height=42, font=16):
        return FlowLabel(text=text, color=INK, font=font, minimum=height)

    def build(self):
        Window.clearcolor = (.96, .97, 1, 1)
        Window.softinput_mode = 'below_target'
        self.store = Store(self.user_data_dir)
        self.bridge = AndroidBridge(self.user_data_dir, self.message)
        self.mode, self.viewing = 'walk', None
        self.signature, self.follow = None, True
        self.preview = None
        self.map_popup = None
        self.zoom_controls = []
        self.map_loaded, self.map_error = False, ''
        self.position_note = 'Visão geral. Toque em Centralizar GPS para encontrar sua posição.'
        self.root_box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(12))
        self.root_box.add_widget(self.label('passo', 45, 23))
        nav = ContentRow(spacing=dp(6))
        nav.add_widget(self.button('Atividade', self.active_home))
        nav.add_widget(self.button('Histórico', self.history))
        nav.add_widget(self.button('Sobre', self.about))
        self.navigation = nav
        self.body = BoxLayout(orientation='vertical', spacing=dp(7))
        self.root_box.add_widget(self.body)
        self.root_box.add_widget(self.navigation)
        cache_dir = Path(self.user_data_dir)/'tiles'
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.map_source = ReliableMapSource(cache_dir, self.map_status, certifi.where())
        self.mapview = PageMap(zoom=1, lat=20, lon=0, map_source=self.map_source,
                              cache_dir=str(cache_dir), background_color=(.92, .94, .91, 1))
        self.map_source.cache_dir = str(cache_dir)
        self.route = RouteLayer()
        self.mapview.add_layer(self.route, mode='window')
        self.mapview.bind(on_touch_down=self.map_touched)
        self.mapview.bind(zoom=self.sync_zoom_controls)
        self.home()
        Window.bind(size=self.resize_content)
        Clock.schedule_once(lambda dt: self.locate(prompt=False), 1)
        Clock.schedule_interval(self.refresh, 1)
        return self.root_box

    def message(self, text):
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.label(str(text), 80))
        box.add_widget(scroll)
        popup = Popup(title='Passo', size_hint=(.94, .75), content=box)
        box.add_widget(self.button('Fechar', popup.dismiss))
        popup.open()

    def confirm(self, text, callback):
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.label(text, 60))
        box.add_widget(scroll)
        popup = Popup(title='Confirmar', content=box, size_hint=(.94, .75))
        box.add_widget(self.button('Confirmar', lambda: (popup.dismiss(), callback())))
        box.add_widget(self.button('Cancelar', popup.dismiss))
        popup.open()

    def scroll_content(self):
        self.body.clear_widgets()
        scroll = MapScrollView(do_scroll_x=False, bar_width=dp(5),
                            effect_cls=ScrollEffect,
                            scroll_type=['content', 'bars'], always_overscroll=False,
                            scroll_distance=dp(12), scroll_timeout=180)
        box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(14),
                        padding=(dp(2), dp(4), dp(7), dp(16)))
        box.bind(minimum_height=box.setter('height'))
        scroll.add_widget(box)
        self.body.add_widget(scroll)
        self.page_scroll, self.content = scroll, box
        return box

    def home(self):
        self.page = 'home'
        # Detach the map before disposing the old layout.
        if self.mapview.parent:
            self.mapview.parent.remove_widget(self.mapview)
        content = self.scroll_content()
        greeting = self.label('Sua próxima conquista começa aqui', 28, 13)
        greeting.color = MUTED
        content.add_widget(greeting)
        heading = self.label('Vamos nos movimentar?', 40, 25)
        heading.bold = True
        content.add_widget(heading)
        self.setup = Card()
        self.setup.bind(minimum_height=self.fit_setup)
        modes = ContentRow(spacing=dp(5))
        self.walk = self.button('Caminhada', lambda: self.choose('walk'))
        self.run = self.button('Corrida', lambda: self.choose('run'))
        modes.add_widget(self.walk)
        modes.add_widget(self.run)
        self.setup.add_widget(modes)
        weightrow = ContentRow()
        weightrow.add_widget(self.label('Seu peso (kg)', 45))
        self.weight = TextInput(text=str(self.store.get('weight', 70)), multiline=False, input_type='number',
                                size_hint_y=None, height=dp(48))
        self.weight.bind(focus=self.focus_weight)
        weightrow.add_widget(self.weight)
        self.setup.add_widget(weightrow)
        content.add_widget(self.setup)
        self.stats = self.label('', 48, 29)
        self.stats.bold = True
        self.status = self.label('', 50, 14)
        summary = Card()
        caption = self.label('SUA ATIVIDADE', 24, 11)
        caption.color = MUTED
        summary.add_widget(caption)
        summary.add_widget(self.stats)
        self.metrics = self.label('', 45, 14)
        self.metrics.color = MUTED
        summary.add_widget(self.metrics)
        summary.add_widget(self.status)
        content.add_widget(summary)
        self.actions = ContentRow(spacing=dp(6))
        self.action_signature = None
        content.add_widget(self.actions)
        self.toggle = self.button('', self.toggle_map)
        content.add_widget(self.toggle)
        self.mapbox = Card()
        self.mapbox.bind(minimum_height=self.fit_mapbox)
        self.mapnote = self.label('', 52, 12)
        self.mapbox.add_widget(self.mapnote)
        self.map_frame = BoxLayout(size_hint_y=None, height=dp(280))
        self.map_frame.add_widget(self.mapview)
        self.page_scroll.map_target = self.mapview
        self.mapbox.add_widget(self.map_frame)
        self.zoom_controls = []
        self.mapbox.add_widget(self.zoom_row())
        self.mapbox.add_widget(self.label('No mapa: arraste com um dedo e ajuste o zoom com dois. Fora do mapa: arraste para rolar a tela.', 42, 12))
        map_controls = ContentRow(spacing=dp(5))
        map_controls.add_widget(self.button('Centralizar GPS', self.center))
        map_controls.add_widget(self.button('Atualizar mapa', self.reload_map))
        self.mapbox.add_widget(map_controls)
        self.mapbox.add_widget(self.button('Explorar mapa livre', self.explore_map))
        content.add_widget(self.mapbox)
        self.resize_content()
        self.apply_map()
        self.choose(self.mode)
        self.refresh()
        self.update_map_note()

    def fit_setup(self, *_):
        self.setup.height = 0 if self.setup.disabled else self.setup.minimum_height

    def fit_mapbox(self, *_):
        self.mapbox.height = self.mapbox.minimum_height if self.store.get('map_open', True) else 0

    def resize_content(self, *_):
        if hasattr(self, 'map_frame'):
            self.map_frame.height = max(dp(200), min(dp(400), Window.height*.40))

    def focus_weight(self, widget, focused):
        if focused:
            Clock.schedule_once(lambda dt: self.page_scroll.scroll_to(widget, padding=dp(16), animate=False), .25)

    def explore_map(self):
        if self.map_popup:
            return
        # Exploring is deliberate: new GPS points must not pull the camera back.
        self.follow = False
        self.map_frame.remove_widget(self.mapview)
        self.mapview.interactive = True
        box = BoxLayout(orientation='vertical', spacing=dp(7), padding=dp(6))
        popup = Popup(title='GPS • mapa livre', size_hint=(.98, .96), content=box, auto_dismiss=False)
        self.map_popup = popup
        box.add_widget(self.button('Voltar para a atividade', popup.dismiss))
        hint = self.label('Arraste com um dedo para explorar. Afaste ou junte dois dedos para ajustar o zoom.', 42, 12)
        hint.color = (.95, .97, .95, 1)
        box.add_widget(hint)
        box.add_widget(self.mapview)
        zoom_row = self.zoom_row()
        self.popup_zoom_pair = self.zoom_controls[-1]
        box.add_widget(zoom_row)
        controls = ContentRow(spacing=dp(6))
        controls.add_widget(self.button('Minha posição GPS', self.center))
        controls.add_widget(self.button('Atualizar mapa', self.reload_map))
        box.add_widget(controls)
        popup.bind(on_dismiss=self.close_map_popup)
        popup.open()
        Clock.schedule_once(lambda dt: self.mapview.trigger_update(True), .1)

    def close_map_popup(self, *_):
        self.mapview.parent.remove_widget(self.mapview)
        self.mapview.interactive = True
        self.map_frame.add_widget(self.mapview)
        self.map_popup = None
        if self.popup_zoom_pair in self.zoom_controls:
            self.zoom_controls.remove(self.popup_zoom_pair)
        Clock.schedule_once(lambda dt: self.mapview.trigger_update(True), .1)

    def zoom_row(self):
        row = ContentRow(spacing=dp(6))
        farther = self.button('− Afastar', lambda: self.zoom_map(-1))
        closer = self.button('+ Aproximar', lambda: self.zoom_map(1))
        row.add_widget(farther)
        row.add_widget(closer)
        self.zoom_controls.append((farther, closer))
        self.sync_zoom_controls()
        return row

    def zoom_map(self, direction):
        self.follow = False
        source = self.mapview.map_source
        target = int(self.mapview.zoom)+direction
        self.mapview.zoom = max(source.min_zoom, min(source.max_zoom, target))
        self.sync_zoom_controls()

    def sync_zoom_controls(self, *_):
        if not hasattr(self, 'mapview'):
            return
        source = self.mapview.map_source
        for farther, closer in self.zoom_controls:
            farther.disabled = self.mapview.zoom <= source.min_zoom
            closer.disabled = self.mapview.zoom >= source.max_zoom

    def active_home(self):
        self.viewing = None
        self.signature = None
        self.home()

    def choose(self, mode):
        self.mode = mode
        self.walk.fill = BLUE if mode == 'walk' else PALE
        self.run.fill = BLUE if mode == 'run' else PALE
        self.walk.color = (1, 1, 1, 1) if mode == 'walk' else BLUE
        self.run.color = (1, 1, 1, 1) if mode == 'run' else BLUE

    def toggle_map(self):
        self.store.set('map_open', not self.store.get('map_open', True))
        self.apply_map()

    def apply_map(self):
        opened = self.store.get('map_open', True)
        self.toggle.text = 'Fechar mapa GPS' if opened else 'Abrir mapa GPS'
        self.mapbox.opacity = 1 if opened else 0
        self.mapbox.disabled = not opened
        self.fit_mapbox()
        if opened:
            Clock.schedule_once(lambda dt: self.route.reposition(), .1)

    def map_status(self, loaded, error):
        if loaded:
            self.map_loaded = True
            self.map_error = ''
        else:
            self.map_error = error
        self.update_map_note()

    def update_map_note(self):
        if hasattr(self, 'mapnote'):
            self.mapnote.text = (self.map_error or
                (('Mapa carregado. ' if self.map_loaded else 'Carregando mapa pela internet... ') + self.position_note))

    def reload_map(self):
        self.map_loaded, self.map_error = False, ''
        self.update_map_note()
        self.mapview.remove_all_tiles()
        self.mapview.trigger_update(True)

    def locate(self, prompt=True):
        from kivy.utils import platform
        if self.viewing or self.route.points:
            return
        if platform != 'android':
            return
        from android.permissions import Permission, check_permission, request_permissions
        def begin(*_):
            if not check_permission(Permission.ACCESS_FINE_LOCATION):
                if prompt:
                    self.position_note = 'Permita localização precisa para centralizar o mapa.'
                    self.update_map_note()
                return
            from passo.location_preview import LocationPreview
            if self.preview:
                self.preview.stop()
            self.position_note = 'Buscando sua posição GPS...'
            self.update_map_note()
            self.preview = LocationPreview(self.preview_position, self.preview_error)
            self.preview.start()
        if check_permission(Permission.ACCESS_FINE_LOCATION):
            begin()
        elif prompt:
            request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION],
                                lambda *a: Clock.schedule_once(lambda dt: begin(), 0))

    def preview_position(self, lat, lon, accuracy):
        if self.viewing or self.route.points:
            return
        if self.follow:
            self.mapview.zoom = 17
            self.mapview.center_on(lat, lon)
        self.route.preview_fix = {'lat': lat, 'lon': lon}
        self.route.reposition()
        self.position_note = f'Posição encontrada (±{accuracy:.0f} m).'
        self.update_map_note()

    def preview_error(self, message):
        self.position_note = message
        self.update_map_note()

    def map_touched(self, widget, touch):
        if widget.interactive and widget.collide_point(*touch.pos):
            self.follow = False

    def center(self):
        self.follow = True
        points = self.route.points
        if points:
            self.mapview.zoom = 17
            self.mapview.center_on(points[-1]['lat'], points[-1]['lon'])
            self.position_note = 'Exibindo o percurso registrado.'
            self.update_map_note()
        else:
            self.locate()

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
        self.stats.text = f'{clock(duration)}'
        self.metrics.text = (f'{distance/1000:.2f} km     •     {a.get("kcal", 0):.0f} kcal\n'
                             f'{pace_text} min/km     •     {distance/duration*3600 if duration else 0:.1f} km/h')
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
        self.fit_setup()
        running = a.get('status') == 'running' and not interrupted
        action_signature = (bool(self.viewing), bool(active), running)
        if self.action_signature != action_signature:
            self.action_signature = action_signature
            self.actions.clear_widgets()
            if self.viewing:
                self.actions.add_widget(self.button('Voltar ao histórico', self.history))
            elif active:
                self.actions.add_widget(self.button('Pausar' if running else 'Retomar',
                                                    lambda: self.send('pause' if running else 'resume')))
                self.actions.add_widget(self.button('Parar e salvar', lambda: self.confirm(
                    'Encerrar o GPS e salvar a atividade?', lambda: self.send('finish'))))
            else:
                self.actions.add_widget(self.button('Iniciar atividade', self.start))
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
        title = self.label('Suas conquistas', 48, 26)
        title.bold = True
        box.add_widget(title)
        records = self.store.history()
        if not records:
            box.add_widget(self.label('Suas atividades salvas aparecerão aqui.', 80))
        for a in records:
            title = 'Corrida' if a['mode'] == 'run' else 'Caminhada'
            date = datetime.fromtimestamp(a['date']/1000).strftime('%d/%m/%Y %H:%M')
            card = Card()
            box.add_widget(card)
            card.add_widget(self.label(f'{title} · {date}\n{a["distance"]/1000:.2f} km · {clock(a["duration"])}', 70))
            card.add_widget(self.button('Ver percurso', lambda a=a: self.view(a)))
            card.add_widget(self.button('Exportar GPX', lambda a=a: self.export(a)))
            card.add_widget(self.button('Apagar', lambda a=a: self.confirm('Apagar esta atividade?',
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
        if self.preview:
            self.preview.stop()
        return True

    def on_resume(self):
        self.refresh()
        self.locate(prompt=False)


if __name__ == '__main__':
    PassoApp().run()
