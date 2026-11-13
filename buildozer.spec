[app]
title = TeaGuardian
package.name = teaguardian
package.domain = com.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = client/**
source.exclude_dirs = .venv,.buildozer,.git,.github,bin,__pycache__,docs,tests,server,~

version = 0.1.0
requirements = python3,kivy==2.3.0,requests,urllib3,idna,certifi,charset-normalizer

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.extra_manifest_application_arguments = extra_manifest_application_arguments.xml
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
