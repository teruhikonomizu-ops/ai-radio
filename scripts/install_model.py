# -*- coding: utf-8 -*-
"""AivisHubの音声モデルをローカルのAivisSpeech Engineにインストールする。
使い方: python install_model.py <モデルUUID>
モデル探し: https://hub.aivis-project.com/ (声のサンプルを試聴できる)
"""
import sys
import uuid
import urllib.request

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
model_uuid = sys.argv[1]
dl = f"https://api.aivis-project.com/v1/aivm-models/{model_uuid}/download?model_type=AIVMX"

boundary = uuid.uuid4().hex
body = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="url"\r\n\r\n'
    f"{dl}\r\n"
    f"--{boundary}--\r\n"
).encode()
req = urllib.request.Request(
    "http://127.0.0.1:10101/aivm_models/install",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=1800) as r:
        print("install OK:", r.status)
except urllib.error.HTTPError as e:
    print("ERROR:", e, e.read()[:500])
    sys.exit(1)
