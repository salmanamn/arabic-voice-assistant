"""helm test: one spoken turn through the gateway, from inside the cluster (M5).

tts speaks a fixed question, the gateway gets it as a recording: stt -> chat -> tts. Passes when the gateway heard
something, answered something and returned a WAV. Prints what was heard and answered for a human to judge, and
the timings of each stage."""

import base64
import sys
import time

import httpx2 as httpx  # the HTTP client of the gateway image (openai uses it)

QUESTION = "ما هي عاصمة مملكة البحرين؟"

with httpx.Client(timeout=300.0) as client:
    for attempt in range(10):  # a new pod's network policy can take a few seconds to be programmed
        try:
            spoken = client.post("http://tts:8000/v1/audio/speech", json={"input": QUESTION, "response_format": "wav"})
            break
        except httpx.ConnectError:
            if attempt == 9:
                raise
            time.sleep(2)
    spoken.raise_for_status()
    response = client.post(
        "http://gateway:8080/api/turn", files={"file": ("question.wav", spoken.content, "audio/wav")}
    )

body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
audio = base64.b64decode(body.get("audio") or "")
checks = {
    "status 200": response.status_code == 200,
    "heard something": bool(body.get("heard")),
    "answered something": bool(body.get("answer")),
    "answer audio is a WAV": audio[:4] == b"RIFF" and audio[8:12] == b"WAVE",
}
print(f"asked:    {QUESTION}")
print(f"heard:    {body.get('heard', '')}")
print(f"answered: {body.get('answer', '')}")
print(f"timings:  {body.get('timings') or body.get('error')}")
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} {name}")
sys.exit(0 if all(checks.values()) else 1)
