"""Android permissions, foreground-service startup, and GPX document picker."""
import json
from pathlib import Path
from kivy.clock import Clock
from kivy.utils import platform


class AndroidBridge:
    def __init__(self, folder, message):
        self.folder, self.message = folder, message
        self.pending = None
        if platform == 'android':
            from android import activity
            activity.bind(on_activity_result=self.result)

    def ready(self, callback):
        if platform != 'android':
            self.message('O GPS real funciona no APK Android. Este modo é apenas uma prévia.')
            return
        from android.permissions import Permission, check_permission, request_permissions
        from jnius import autoclass
        def checked(*args):
            if not check_permission(Permission.ACCESS_FINE_LOCATION):
                self.message('Permita localização precisa para registrar o percurso.')
                return
            ctx = autoclass('org.kivy.android.PythonActivity').mActivity
            if not ctx.getSystemService('location').isProviderEnabled('gps'):
                self.message('Ative a localização do celular e tente novamente.')
                return
            if (autoclass('android.os.Build$VERSION').SDK_INT >= 33
                    and not check_permission('android.permission.POST_NOTIFICATIONS')):
                request_permissions(['android.permission.POST_NOTIFICATIONS'],
                                    lambda *a: Clock.schedule_once(lambda dt: callback(), 0))
            else:
                callback()
        if check_permission(Permission.ACCESS_FINE_LOCATION):
            checked()
        else:
            request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION],
                                lambda *a: Clock.schedule_once(lambda dt: checked(), 0))

    def launch(self):
        from jnius import autoclass
        ctx = autoclass('org.kivy.android.PythonActivity').mActivity
        cls = autoclass('br.com.passo.python.ServiceTracking')
        cls.start(ctx, '', 'Passo', 'Registro de caminhada ou corrida em andamento',
                  json.dumps({'folder': self.folder}))

    def export(self, identity, content):
        if platform != 'android':
            target = Path(self.folder)/f'passo-{identity}.gpx'
            target.write_bytes(content)
            self.message(f'GPX salvo em {target}')
            return
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        self.pending = content
        @run_on_ui_thread
        def picker():
            intent = autoclass('android.content.Intent')('android.intent.action.CREATE_DOCUMENT')
            intent.setType('application/gpx+xml')
            intent.addCategory('android.intent.category.OPENABLE')
            intent.putExtra('android.intent.extra.TITLE', f'passo-{identity}.gpx')
            autoclass('org.kivy.android.PythonActivity').mActivity.startActivityForResult(intent, 40)
        picker()

    def result(self, request, result, data):
        if request != 40:
            return
        content, self.pending = self.pending, None
        if result != -1 or data is None or content is None:
            return
        try:
            from jnius import autoclass
            ctx = autoclass('org.kivy.android.PythonActivity').mActivity
            stream = ctx.getContentResolver().openOutputStream(data.getData())
            try:
                stream.write(bytearray(content))
            finally:
                stream.close()
            text = 'Percurso exportado.'
        except Exception:
            text = 'Não foi possível salvar o GPX.'
        Clock.schedule_once(lambda dt: self.message(text), 0)
