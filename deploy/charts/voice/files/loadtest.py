"""Load on stt from inside the cluster, to watch the autoscaler (M5 Step 4).

WORKERS threads send the same spoken question to the stt Service for SECONDS, each call on a new connection, so
the Service spreads them over every ready replica. Every 15 s: calls done, 503 busy, other errors, p50 latency."""

import os
import statistics
import threading
import time

import httpx2 as httpx  # the HTTP client of the gateway image (openai uses it)

WORKERS, SECONDS = int(os.environ["WORKERS"]), int(os.environ["SECONDS"])
QUESTION = "ما هي عاصمة مملكة البحرين؟ وما هي أكبر مدينة فيها؟"
NO_KEEPALIVE = httpx.Limits(max_keepalive_connections=0)

for attempt in range(10):  # a new pod's network policy can take a few seconds to be programmed
    try:
        audio = httpx.post("http://tts:8000/v1/audio/speech", json={"input": QUESTION}, timeout=120).content
        break
    except httpx.ConnectError:
        if attempt == 9:
            raise
        time.sleep(2)
lock = threading.Lock()
window: dict = {"ok": [], "busy": 0, "error": 0}
stop = time.monotonic() + SECONDS


def worker() -> None:
    with httpx.Client(timeout=120, limits=NO_KEEPALIVE) as client:
        while time.monotonic() < stop:
            started = time.perf_counter()
            try:
                response = client.post(
                    "http://stt:8000/v1/audio/transcriptions",
                    files={"file": ("q.wav", audio, "audio/wav")},
                    data={"language": "ar"},
                )
                kind = "ok" if response.status_code == 200 else "busy" if response.status_code == 503 else "error"
            except httpx.HTTPError:
                kind = "error"
            with lock:
                if kind == "ok":
                    window["ok"].append(time.perf_counter() - started)
                else:
                    window[kind] += 1
            if kind == "busy":
                time.sleep(1)  # as a client should after 503 busy


threads = [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
for thread in threads:
    thread.start()
print(f"{WORKERS} workers for {SECONDS} s against stt, {len(audio)} bytes of audio per call", flush=True)
began = time.monotonic()
while any(thread.is_alive() for thread in threads):
    time.sleep(15)
    with lock:
        done, busy, error = window["ok"], window["busy"], window["error"]
        window.update(ok=[], busy=0, error=0)
    p50 = statistics.median(done) if done else 0.0
    print(
        f"t={time.monotonic() - began:5.0f} s  ok {len(done):3d}  busy {busy:3d}  error {error:3d}  p50 {p50:5.2f} s",
        flush=True,
    )
print("done", flush=True)
