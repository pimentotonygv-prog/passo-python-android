"""Tracking logic independent of Android; times are milliseconds unless noted."""
import copy
import math
import time
import uuid
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring


def meters(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    dlat = lat2 - lat1
    dlon = math.radians(b['lon'] - a['lon'])
    q = math.sin(dlat / 2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon / 2)**2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, q))))


def calories(mode, weight, duration):
    return (7.5 if mode == 'run' else 3.8) * 3.5 * weight / 200 * duration / 60000


class Tracker:
    def __init__(self, saved=None, monotonic=time.monotonic, wall=time.time):
        self.mono, self.wall = monotonic, wall
        self.active = copy.deepcopy(saved) if saved else None
        self.started = None
        self.last = None
        self.last_signal_elapsed = None
        self.recording_since = None
        self.segment = int((saved or {}).get('segment', 0))
        if self.active:
            self.active['status'] = 'interrupted'

    def start(self, mode, weight):
        weight = float(weight)
        if mode not in ('walk', 'run') or not math.isfinite(weight) or not 20 <= weight <= 300:
            raise ValueError('Informe um peso entre 20 e 300 kg.')
        if self.active:
            raise ValueError('Finalize ou retome a atividade atual.')
        self.active = dict(id=uuid.uuid4().hex, date=int(self.wall()*1000), mode=mode,
                           weight=weight, duration=0, distance=0, points=[], status='paused')
        self.resume()

    def resume(self):
        if not self.active or self.started is not None:
            return
        self.segment += 1
        self.last = None
        self.started = self.mono()
        self.recording_since = self.wall()*1000
        self.last_signal_elapsed = None
        self.active['status'] = 'running'
        self.active.pop('error', None)

    def pause(self):
        if self.active and self.started is not None:
            self.active['duration'] += max(0, self.mono()-self.started)*1000
            self.started = None
        self.last = None
        if self.active:
            self.active['status'] = 'paused'

    def snapshot(self):
        if not self.active:
            return {}
        result = copy.deepcopy(self.active)
        if self.started is not None:
            result['duration'] += max(0, self.mono()-self.started)*1000
        result['segment'] = self.segment
        result['kcal'] = calories(result['mode'], result['weight'], result['duration'])
        return result

    def finish(self):
        self.pause()
        result = self.snapshot()
        if result:
            result['status'] = 'finished'
        self.active = None
        return result

    def location(self, lat, lon, accuracy, elapsed, age=0, speed=None, timestamp=None):
        """elapsed/age are seconds from Android elapsedRealtime (not wall clock)."""
        if self.started is None:
            return False
        values = (lat, lon, accuracy, elapsed, age)
        if not all(math.isfinite(v) for v in values):
            return False
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 < accuracy <= 15 and 0 <= age <= 5):
            return False
        if self.last_signal_elapsed is not None and elapsed <= self.last_signal_elapsed:
            return False
        if timestamp is not None and (not math.isfinite(timestamp) or timestamp < self.recording_since):
            return False
        if speed is not None and (not math.isfinite(speed) or speed < 0):
            speed = None
        p = dict(lat=lat, lon=lon, accuracy=accuracy, elapsed=elapsed,
                 time=int(timestamp if timestamp is not None else self.wall()*1000))
        distance = 0
        if self.last:
            seconds = elapsed-self.last['elapsed']
            if seconds <= 0:
                return False
            distance = meters(self.last, p)
            signal_gap = elapsed-(self.last_signal_elapsed if self.last_signal_elapsed is not None else self.last['elapsed'])
            if signal_gap > 8:
                self.segment += 1
                distance = 0
            else:
                if distance/seconds > (9 if self.active['mode'] == 'run' else 4.5):
                    return False
                self.note_signal(accuracy, elapsed)
                # Keep short walking steps and corners; never average across a turn.
                threshold = max(.75, min(1.5, min(accuracy, self.last['accuracy'])*0.1))
                if distance < threshold:
                    return False
                if speed is not None and speed < 0.35 and distance < max(3, accuracy*0.6):
                    return False
        self.note_signal(accuracy, elapsed)
        p['seg'] = self.segment
        self.active['points'].append(p)
        self.active['distance'] += distance
        self.active['accuracy'] = accuracy
        self.active['lastFix'] = int(self.wall()*1000)
        self.active.pop('error', None)
        self.last = p
        return True

    def note_signal(self, accuracy, elapsed):
        self.last_signal_elapsed = elapsed
        self.active['accuracy'] = accuracy
        self.active['lastSignal'] = int(self.wall()*1000)



def to_gpx(activity):
    if not activity.get('points'):
        raise ValueError('Esta atividade não tem pontos de GPS.')
    root = Element('gpx', version='1.1', creator='Passo Python', xmlns='http://www.topografix.com/GPX/1/1')
    track = SubElement(root, 'trk')
    SubElement(track, 'name').text = 'Corrida' if activity['mode'] == 'run' else 'Caminhada'
    segment_id, segment = object(), None
    for p in activity['points']:
        if segment_id != p.get('seg', 0):
            segment_id = p.get('seg', 0)
            segment = SubElement(track, 'trkseg')
        point = SubElement(segment, 'trkpt', lat=str(p['lat']), lon=str(p['lon']))
        SubElement(point, 'time').text = datetime.fromtimestamp(p['time']/1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return tostring(root, encoding='utf-8', xml_declaration=True)
