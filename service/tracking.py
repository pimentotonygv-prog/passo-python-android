"""Android foreground service. Never import Kivy UI here."""
import json
import os
import threading
import time

from jnius import PythonJavaClass, autoclass, java_method
from passo.core import Tracker
from passo.storage import Store

service = autoclass('org.kivy.android.PythonService').mService
store = Store(json.loads(os.environ['PYTHON_SERVICE_ARGUMENT'])['folder'])
tracker = Tracker(store.get('active'))
guard = threading.RLock()
lm = service.getSystemService('location')
clock = autoclass('android.os.SystemClock')
thread = autoclass('android.os.HandlerThread')('PassoGPS')
thread.start()
wake = service.getSystemService('power').newWakeLock(1, 'passopy:tracking')
wake.setReferenceCounted(False)


class Listener(PythonJavaClass):
    __javainterfaces__ = ['android/location/LocationListener']
    __javacontext__ = 'app'

    @java_method('(Landroid/location/Location;)V')
    def onLocationChanged(self, loc):
        if not loc.hasAccuracy():
            return
        with guard:
            tracker.location(loc.getLatitude(), loc.getLongitude(), loc.getAccuracy(),
                             loc.getElapsedRealtimeNanos()/1e9,
                             age=(clock.elapsedRealtimeNanos()-loc.getElapsedRealtimeNanos())/1e9,
                             speed=loc.getSpeed() if loc.hasSpeed() else None,
                             timestamp=loc.getTime())

    @java_method('(Ljava/lang/String;)V')
    def onProviderDisabled(self, provider):
        with guard:
            if tracker.active:
                tracker.active['error'] = 'GPS desligado. Ative a localização do celular.'

    @java_method('(Ljava/lang/String;)V')
    def onProviderEnabled(self, provider):
        pass

    @java_method('(Ljava/lang/String;ILandroid/os/Bundle;)V')
    def onStatusChanged(self, provider, status, extras):
        pass


listener = Listener()  # Strong reference for Java callbacks.
subscribed = False


def subscribe():
    global subscribed
    if not lm.isProviderEnabled('gps'):
        raise ValueError('Ative a localização do celular antes de iniciar.')
    if not subscribed:
        lm.requestLocationUpdates('gps', 1000, 0.0, listener, thread.getLooper())
        subscribed = True
    if not wake.isHeld():
        wake.acquire()


def unsubscribe():
    global subscribed
    lm.removeUpdates(listener)
    subscribed = False
    if wake.isHeld():
        wake.release()


store.set('service_error', '')
try:
    while True:
        with guard:
            for cmd in store.commands():
                try:
                    action = cmd['action']
                    if action == 'start':
                        tracker.start(cmd['mode'], cmd['weight'])
                        subscribe()
                    elif action == 'resume':
                        tracker.resume()
                        subscribe()
                    elif action == 'pause':
                        tracker.pause()
                        unsubscribe()
                    elif action == 'finish':
                        unsubscribe()
                        result = tracker.finish()
                        if result:
                            store.archive(result)
                    else:
                        raise ValueError('Comando desconhecido.')
                    store.set('service_error', '')
                except Exception as exc:
                    tracker.pause()
                    unsubscribe()
                    store.set('service_error', str(exc))
            store.checkpoint(tracker.snapshot())
            if not tracker.active:
                break
        time.sleep(1)
finally:
    with guard:
        tracker.pause()
        store.checkpoint(tracker.snapshot())
    unsubscribe()
    thread.quitSafely()
    service.stopSelf()
