# NetworkPolicy check (M5)

Namespace `voice`; `scripts/check_netpol.py --outside 1.1.1.1:443`. Connections from inside each pod
to the Services' cluster IPs; probe pods carry the labels of the jobs and the test pod.

| From | To | Expected | Seen | |
|---|---|---|---|---|
| gateway | stt | open | open | OK |
| gateway | tts | open | open | OK |
| gateway | ollama | open | open | OK |
| gateway | outside (1.1.1.1:443) | closed | closed | OK |
| gateway | kube-api (10.96.0.1:443) | closed | closed | OK |
| stt | tts | closed | closed | OK |
| stt | gateway | closed | closed | OK |
| stt | ollama | closed | closed | OK |
| stt | outside (1.1.1.1:443) | closed | closed | OK |
| stt | kube-api (10.96.0.1:443) | closed | closed | OK |
| tts | stt | closed | closed | OK |
| tts | gateway | closed | closed | OK |
| tts | ollama | closed | closed | OK |
| tts | outside (1.1.1.1:443) | closed | closed | OK |
| tts | kube-api (10.96.0.1:443) | closed | closed | OK |
| ollama | stt | closed | closed | OK |
| ollama | tts | closed | closed | OK |
| ollama | gateway | closed | closed | OK |
| ollama | outside (1.1.1.1:443) | closed | closed | OK |
| ollama | kube-api (10.96.0.1:443) | closed | closed | OK |
| models (job) | stt | closed | closed | OK |
| models (job) | tts | closed | closed | OK |
| models (job) | gateway | closed | closed | OK |
| models (job) | ollama | closed | closed | OK |
| models (job) | outside (1.1.1.1:443) | open | open | OK |
| models (job) | kube-api (10.96.0.1:443) | closed | closed | OK |
| test (helm test) | stt | closed | closed | OK |
| test (helm test) | tts | open | open | OK |
| test (helm test) | gateway | open | open | OK |
| test (helm test) | ollama | closed | closed | OK |
| test (helm test) | outside (1.1.1.1:443) | closed | closed | OK |
| test (helm test) | kube-api (10.96.0.1:443) | closed | closed | OK |
| loadtest | stt | open | open | OK |
| loadtest | tts | open | open | OK |
| loadtest | gateway | closed | closed | OK |
| loadtest | ollama | closed | closed | OK |
| loadtest | outside (1.1.1.1:443) | closed | closed | OK |
| loadtest | kube-api (10.96.0.1:443) | closed | closed | OK |
| unknown pod | stt | closed | closed | OK |
| unknown pod | tts | closed | closed | OK |
| unknown pod | gateway | closed | closed | OK |
| unknown pod | ollama | closed | closed | OK |
| unknown pod | outside (1.1.1.1:443) | closed | closed | OK |
| unknown pod | kube-api (10.96.0.1:443) | closed | closed | OK |

44/44 flows as expected.
