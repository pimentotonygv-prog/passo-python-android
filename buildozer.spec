[app]
title = Passo Python
package.name = python
package.domain = br.com.passo
source.dir = .
source.include_exts = py,png,kv
source.exclude_dirs = tests,.github,bin,.venv,__pycache__
version = 2.0.0
requirements = python3,kivy,pyjnius,sqlite3,kivy_garden.mapview,requests,openssl,certifi
orientation = portrait
fullscreen = 0
services = Tracking:service/tracking.py:foreground:foregroundServiceType=location
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,POST_NOTIFICATIONS,WAKE_LOCK
android.api = 36
android.minapi = 26
android.ndk = 28c
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = False
android.accept_sdk_license = False
android.debug_artifact = apk
android.release_artifact = apk
p4a.branch = v2026.05.09

[buildozer]
log_level = 2
warn_on_root = 1
