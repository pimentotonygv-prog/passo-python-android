"""One-shot visible-screen location preview, separate from recorded workouts."""
from kivy.clock import Clock
from jnius import PythonJavaClass, autoclass, java_method


class PreviewListener(PythonJavaClass):
    __javainterfaces__ = ['android/location/LocationListener']
    __javacontext__ = 'app'

    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    @java_method('(Landroid/location/Location;)V')
    def onLocationChanged(self, loc):
        self.owner.received(loc)

    @java_method('(Ljava/lang/String;)V')
    def onProviderDisabled(self, provider):
        pass

    @java_method('(Ljava/lang/String;)V')
    def onProviderEnabled(self, provider):
        pass

    @java_method('(Ljava/lang/String;ILandroid/os/Bundle;)V')
    def onStatusChanged(self, provider, status, extras):
        pass


class LocationPreview:
    def __init__(self, success, failure):
        self.success, self.failure = success, failure
        self.manager = autoclass('org.kivy.android.PythonActivity').mActivity.getSystemService('location')
        self.listener = PreviewListener(self)
        self.finished = True
        self.starting = False
        self.timeout = None

    def start(self):
        self.stop()
        self.finished = False
        self.starting = True
        loop = autoclass('android.os.Looper').getMainLooper()
        try:
            available = [p for p in ('gps', 'network') if self.manager.isProviderEnabled(p)]
            if not available:
                raise ValueError('Ative a localização do celular para centralizar o mapa.')
            # Request live fixes as well; an old cached position is not current GPS.
            for provider in available:
                self.manager.requestLocationUpdates(provider, 1000, 0.0, self.listener, loop)
            self.timeout = Clock.schedule_once(self.timed_out, 30)
            self.starting = False
            fixes = [self.manager.getLastKnownLocation(p) for p in available]
            fixes = [p for p in fixes if p is not None]
            fixes.sort(key=lambda p: p.getElapsedRealtimeNanos(), reverse=True)
            for fix in fixes:
                if self.received(fix):
                    break
        except Exception as exc:
            self.stop()
            self.failure(str(exc))

    def received(self, loc):
        elapsed = autoclass('android.os.SystemClock').elapsedRealtimeNanos()
        age = (elapsed-loc.getElapsedRealtimeNanos())/1e9
        if self.finished or self.starting or not loc.hasAccuracy() or not 0 < loc.getAccuracy() <= 100 or not 0 <= age <= 15:
            return False
        position = (loc.getLatitude(), loc.getLongitude(), loc.getAccuracy())
        # Stop before dispatch so simultaneous provider callbacks cannot overwrite.
        self.stop()
        Clock.schedule_once(lambda dt: self.success(*position), 0)
        return True

    def timed_out(self, *_):
        self.stop()
        self.failure('Ainda sem posição recente. Vá para um local aberto e toque em Centralizar GPS.')

    def stop(self):
        self.finished = True
        if self.timeout:
            self.timeout.cancel()
            self.timeout = None
        self.manager.removeUpdates(self.listener)
