# The M9 Azure AI Speech session (D59, D60)

Start 2026-11-20T21:40:54Z. Runs: apply 44822541888, deploy-chart 44831396605, destroy 44838059860; images from ci.yml run 44812023994.

## preflight.txt
```
preflight 2026-11-20T21:26:49Z, main 1cc43eb
images run 44812023994: success main at 1cc43eb36a78, HEAD 1cc43eb36a78
budget lab-budget (amount spent forecast unit): 20.0	2.361666689425419	None	USD
quota uaenorth: Total Regional vCPUs	0	10
quota uaenorth: Standard Falsv6 Family vCPUs	0	10
gpt-5.4-mini: GenerallyAvailable	2027-09-21T00:00:00Z
aks minor offered: 1.36
speech skus uaenorth: F0 S0 apply identity may assign Speech User (condition clauses): 2
hf host: OK   huggingface.co
hf host: OK   us.aws.cdn.hf.co
own set: 20 recordings, first S01.m4a -> 220546 bytes of 16 kHz WAV
```

## jobs.txt
```
plan success 2026-11-20T21:41:31Z 2026-11-20T21:42:05Z
deploy-chart skipped 2026-11-20T21:41:29Z 2026-11-20T21:41:29Z
apply success 2026-11-20T21:42:27Z 2026-11-20T21:47:45Z
```

## resources.txt
```
Name                    Kind
----------------------  --------------
spch-voice-azure-mg4cq  SpeechServices
oai-voice-azure-mg4cq   OpenAI
acrvoiceazuremg4cq
aks-voice-azure
id-voice-azure-gateway
{
  "endpoint": "https://spch-voice-azure-mg4cq.cognitiveservices.azure.com/",
  "localAuthDisabled": true,
  "name": "spch-voice-azure-mg4cq",
  "outboundRestricted": true,
  "sku": "S0"
}
```

## roles.txt
```
Role                                         Scope
-------------------------------------------  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
Azure Kubernetes Service RBAC Admin          Microsoft.ContainerService/managedClusters/aks-voice-azure/namespaces/voice
Cognitive Services Speech User               Microsoft.CognitiveServices/accounts/spch-voice-azure-mg4cq
AcrPull                                      Microsoft.ContainerRegistry/registries/acrvoiceazuremg4cq
Cognitive Services OpenAI User               Microsoft.CognitiveServices/accounts/oai-voice-azure-mg4cq
Azure Kubernetes Service RBAC Cluster Admin  Microsoft.ContainerService/managedClusters/aks-voice-azure
Cognitive Services OpenAI User               Microsoft.CognitiveServices/accounts/oai-voice-azure-mg4cq
```

## localdns.json
```
{
  "k8s": "1.36.5",
  "localDns": null
}
```

## dns-early.txt
```
nameserver 10.0.0.x
gateway resolves login.microsoftonline.com            20.190.177.x
gateway resolves uaenorth.stt.speech.microsoft.com    20.233.132.x
gateway resolves uaenorth.tts.speech.microsoft.com    20.233.132.x
gateway resolves huggingface.co                       socket.gaierror: [Errno -3] Temporary failure in name resolution
```

## deploy-chart-log.txt
```
PASS status 200
PASS heard something
PASS answered something
PASS answer audio is a WAV
FAIL unknown pod        -> speech 1   expected closed seen error
FAIL unknown pod        -> speech 2   expected closed seen error
65/67 flows as expected
FAIL stt-small: /models/stt-small does not exist
FAIL stt-small: model.bin is missing; stt-small: tokenizer.json is missing; stt-small: vocabulary.txt is missing
FAIL stt-small: model.bin is missing; stt-small: tokenizer.json is missing; stt-small: vocabulary.txt is missing
FAIL tts-ar-kareem-medium: /models/tts-ar-kareem-medium does not exist
FAIL tts-ar-kareem-medium: /models/tts-ar-kareem-medium does not exist
FAIL tts-ar-kareem-medium: /models/tts-ar-kareem-medium does not exist
FAIL tts-ar-kareem-medium: /models/tts-ar-kareem-medium does not exist
FAIL tts-ar-kareem-medium: ar_JO-kareem-medium.onnx is missing; tts-ar-kareem-medium: ar_JO-kareem-medium.onnx.json is missing
PASS status 200
PASS heard something
PASS answered something
PASS answer audio is a WAV
```

## gateway-settings.txt
```
local local ar-BH ar-BH-AliNeural uaenorth.stt.speech.microsoft.com uaenorth.tts.speech.microsoft.com
```

## speech-check.txt
```
OK   synthesis: 100992 bytes of WAV, voice ar-BH-AliNeural
OK   recognition (ar-BH) in 0.73 s: مرحبا، هذا اختبار للصوت.
```

## switch-azure.txt
```
STATUS: deployed
REVISION: 4
```

## unsupported.txt
```
S01.m4a: 400 {"code":"unsupported_audio","message":"the speech service refused the recording"}
```

## switch-pods.txt
```
STATUS: deployed
REVISION: 5
```

## destroy.txt
```
run: https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44838059860 (destroy)
[1mPlan:[0m [0m0 to add, 0 to change, 19 to destroy.
[36;1m  terraform show -no-color tfplan | grep -E '^  # |^Plan:|^No changes' | sed "s/${ARM_SUBSCRIPTION_ID}/***/g"[0m
approved
run succeeded: https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44838059860
Apply complete! Resources: 0 added, 0 changed, 19 destroyed.[0m
OK   az signed in as ffef284a…
OK   rg-voice-azure deleted
OK   rg-voice-azure-nodes deleted
rg-voice-azure exists: false
rg-voice-azure-nodes exists: false
soft-deleted Cognitive accounts: 0
state resources: 0
role assignments left: 0
tagged resources left: 0
```

## notes.txt
```
deploy-chart: netpol 64/67, probe pods expired after 600 s (check_netpol.py sleep -> 1800); full check in C4.5
deploy-chart re-run: 65/67, same probe timeout (CI uses main's script)
login.microsoftonline.com (22.6, 0, 'closed', '')
uaenorth.stt.speech.microsoft.com (21.6, 0, 'closed', '')
uaenorth.tts.speech.microsoft.com (21.5, 0, 'closed', '')
listening: sound is clear
```
