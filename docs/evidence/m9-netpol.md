# NetworkPolicy check (egress fqdn)

Namespace `voice`; `scripts/check_netpol.py --egress fqdn --outside 1.1.1.x:443`.
Connections from inside each pod
to the Services' cluster IPs; probe pods carry the labels of the jobs and the test pod.

| From | To | Expected | Seen | |
|---|---|---|---|---|
| gateway | stt | open | open | OK |
| gateway | tts | open | open | OK |
| gateway | outside (1.1.1.x:443) | closed | closed | OK |
| gateway | kube-api (10.0.0.x:443) | closed | closed | OK |
| gateway | model host (huggingface.co:443) | closed | closed | OK |
| gateway | entra (login.microsoftonline.com:443) | open | open | OK |
| gateway | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | open | open | OK |
| gateway | speech 1 (uaenorth.stt.speech.microsoft.com:443) | open | open | OK |
| gateway | speech 2 (uaenorth.tts.speech.microsoft.com:443) | open | open | OK |
| stt | tts | closed | closed | OK |
| stt | gateway | closed | closed | OK |
| stt | outside (1.1.1.x:443) | closed | closed | OK |
| stt | kube-api (10.0.0.x:443) | closed | closed | OK |
| stt | model host (huggingface.co:443) | closed | closed | OK |
| stt | entra (login.microsoftonline.com:443) | closed | closed | OK |
| stt | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | closed | closed | OK |
| stt | speech 1 (uaenorth.stt.speech.microsoft.com:443) | closed | closed | OK |
| stt | speech 2 (uaenorth.tts.speech.microsoft.com:443) | closed | closed | OK |
| tts | stt | closed | closed | OK |
| tts | gateway | closed | closed | OK |
| tts | outside (1.1.1.x:443) | closed | closed | OK |
| tts | kube-api (10.0.0.x:443) | closed | closed | OK |
| tts | model host (huggingface.co:443) | closed | closed | OK |
| tts | entra (login.microsoftonline.com:443) | closed | closed | OK |
| tts | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | closed | closed | OK |
| tts | speech 1 (uaenorth.stt.speech.microsoft.com:443) | closed | closed | OK |
| tts | speech 2 (uaenorth.tts.speech.microsoft.com:443) | closed | closed | OK |
| models (job) | stt | closed | closed | OK |
| models (job) | tts | closed | closed | OK |
| models (job) | gateway | closed | closed | OK |
| models (job) | outside (1.1.1.x:443) | closed | closed | OK |
| models (job) | kube-api (10.0.0.x:443) | closed | closed | OK |
| models (job) | model host (huggingface.co:443) | open | open | OK |
| models (job) | entra (login.microsoftonline.com:443) | closed | closed | OK |
| models (job) | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | closed | closed | OK |
| models (job) | speech 1 (uaenorth.stt.speech.microsoft.com:443) | closed | closed | OK |
| models (job) | speech 2 (uaenorth.tts.speech.microsoft.com:443) | closed | closed | OK |
| test (helm test) | stt | closed | closed | OK |
| test (helm test) | tts | open | open | OK |
| test (helm test) | gateway | open | open | OK |
| test (helm test) | outside (1.1.1.x:443) | closed | closed | OK |
| test (helm test) | kube-api (10.0.0.x:443) | closed | closed | OK |
| test (helm test) | model host (huggingface.co:443) | closed | closed | OK |
| test (helm test) | entra (login.microsoftonline.com:443) | closed | closed | OK |
| test (helm test) | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | closed | closed | OK |
| test (helm test) | speech 1 (uaenorth.stt.speech.microsoft.com:443) | closed | closed | OK |
| test (helm test) | speech 2 (uaenorth.tts.speech.microsoft.com:443) | closed | closed | OK |
| loadtest | stt | open | open | OK |
| loadtest | tts | open | open | OK |
| loadtest | gateway | closed | closed | OK |
| loadtest | outside (1.1.1.x:443) | closed | closed | OK |
| loadtest | kube-api (10.0.0.x:443) | closed | closed | OK |
| loadtest | model host (huggingface.co:443) | closed | closed | OK |
| loadtest | entra (login.microsoftonline.com:443) | closed | closed | OK |
| loadtest | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | closed | closed | OK |
| loadtest | speech 1 (uaenorth.stt.speech.microsoft.com:443) | closed | closed | OK |
| loadtest | speech 2 (uaenorth.tts.speech.microsoft.com:443) | closed | closed | OK |
| unknown pod | stt | closed | closed | OK |
| unknown pod | tts | closed | closed | OK |
| unknown pod | gateway | closed | closed | OK |
| unknown pod | outside (1.1.1.x:443) | closed | closed | OK |
| unknown pod | kube-api (10.0.0.x:443) | closed | closed | OK |
| unknown pod | model host (huggingface.co:443) | closed | closed | OK |
| unknown pod | entra (login.microsoftonline.com:443) | closed | closed | OK |
| unknown pod | chat host (oai-voice-azure-mg4cq.openai.azure.com:443) | closed | closed | OK |
| unknown pod | speech 1 (uaenorth.stt.speech.microsoft.com:443) | closed | closed | OK |
| unknown pod | speech 2 (uaenorth.tts.speech.microsoft.com:443) | closed | closed | OK |

67/67 flows as expected.
