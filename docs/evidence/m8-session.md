]633;E;echo "# The M8 Azure session ($(cut -c1-10 ~/m8/start))";675f9b5c-ef13-48cb-82f1-3317e4c399a1]633;C# The M8 Azure session (2026-11-20)

Start 2026-11-20T02:04:03Z. Runs: apply , deploy-chart 44660363877, destroy 44667986426; images from ci.yml run 44657470638.

## Preflight
```
preflight 2026-11-19T20:02:07Z, main 9f898c8
pins schedule run null null null
pin_images fix on main: 1
budget lab-budget (amount spent forecast unit): 20.0	0.19872342513653046	None	USD
quota uaenorth: Total Regional vCPUs	0	10
quota uaenorth: Standard Falsv6 Family vCPUs	0	10
{
  "lifecycle": "GenerallyAvailable",
  "model": "gpt-5.4-mini",
  "retires": "2027-09-21T00:00:00Z",
  "skus": [
    "GlobalStandard",
    "GlobalProvisionedManaged"
  ],
  "version": "2026-03-17"
}
openai quota: OpenAI.GlobalStandard.gpt-5.4-mini	0.0	1000.0
{
  "minor": "1.37",
  "patches": [
    "1.37.0",
    "1.37.1"
  ],
  "support": [
    "KubernetesOfficial",
    "AKSLongTermSupport"
  ]
}
hf host: OK   huggingface.co
hf host: OK   us.aws.cdn.hf.co
speech set own: 20 utterances; baseline out/m5/turns-kube.json: 2026-11-17 22:46 UTC
images run 44609553072 success main@f82b14794da9
ghcr voice-gateway: sha256:5fd10c784ed36fd7ff67c8142d556749cc74a652f3a6db6d4f94d8258148ab78ghcr voice-models: sha256:199a055ead570e5cc618a62b61b6450a2a7898374487cd4b963072aa1de9b55bpins dispatch run success 2026-11-19T20:40:22Z
[
  {
    "name": "Standard_F8als_v6",
    "restrictions": [
      "NotAvailableForSubscription"
    ]
  }
]
[
  {
    "family": "StandardFalsv6Family",
    "name": "Standard_F8als_v6",
    "restrictions": [
      {
        "locations": [
          "UAENorth"
        ],
        "reason": "NotAvailableForSubscription",
        "type": "Zone",
        "zones": [
          "1"
        ]
      }
    ]
  },
  {
    "family": "StandardFasv6Family",
    "name": "Standard_F8as_v6",
    "restrictions": [
      {
        "locations": [
          "UAENorth"
        ],
        "reason": "NotAvailableForSubscription",
        "type": "Zone",
        "zones": [
          "1"
        ]
      }
    ]
  }
]
quota uaenorth: Standard Falsv6 Family vCPUs	0	10
quota uaenorth: Standard Fasv6 Family vCPUs	0	10
{
  "minor": "1.36",
  "patches": [
    "1.36.0",
    "1.36.1",
    "1.36.2",
    "1.36.3",
    "1.36.4",
    "1.36.5"
  ],
  "support": [
    "KubernetesOfficial",
    "AKSLongTermSupport"
  ]
}
images run 44609553072 success main@f82b14794da9
```

## Jobs (start, end)
```
deploy-chart success 2026-11-20T02:23:07Z 2026-11-20T02:37:12Z
plan skipped 2026-11-20T02:22:52Z 2026-11-20T02:22:52Z
apply skipped 2026-11-20T02:22:52Z 2026-11-20T02:22:52Z
```
]633;E;echo;675f9b5c-ef13-48cb-82f1-3317e4c399a1]633;C
## Apply: plan and gate
```
[1mPlan:[0m [0m16 to add, 0 to change, 0 to destroy.
[36;1mconftest test --no-color --policy ../../policy plan.json | grep -E "^FAIL|tests,"[0m
26 tests, 26 passed, 0 warnings, 0 failures, 0 exceptions
[36;1m  terraform show -no-color tfplan | grep -E '^  # |^Plan:|^No changes' | sed "s/${ARM_SUBSCRIPTION_ID}/***/g"[0m
```

## What the stack created
```
Name
----------------------
oai-voice-azure-e5cw8
acrvoiceazuree5cw8
aks-voice-azure
id-voice-azure-gateway
      1 Microsoft.Compute/virtualMachineScaleSets
      1 Microsoft.ManagedIdentity/userAssignedIdentities
      1 Microsoft.Network/loadBalancers
      1 Microsoft.Network/networkSecurityGroups
      1 Microsoft.Network/publicIPAddresses
      1 Microsoft.Network/virtualNetworks
      1 Microsoft.Compute/virtualMachineScaleSets
      1 Microsoft.ManagedIdentity/userAssignedIdentities
      1 Microsoft.Network/loadBalancers
      1 Microsoft.Network/networkSecurityGroups
      1 Microsoft.Network/publicIPAddresses
      1 Microsoft.Network/virtualNetworks
{
  "endpoint": "https://oai-voice-azure-e5cw8.openai.azure.com/",
  "localAuthDisabled": true,
  "name": "oai-voice-azure-e5cw8",
  "outboundRestricted": true
}
Name          Model         Version     Sku             TpmK    State
------------  ------------  ----------  --------------  ------  ---------
gpt-5.4-mini  gpt-5.4-mini  2026-03-17  GlobalStandard  50      Succeeded
{
  "acnsSecurity": true,
  "azureRbac": true,
  "dataplane": "cilium",
  "k8s": "1.36.5",
  "localAccountsOff": true,
  "node": "Standard_F8als_v6",
  "nodes": 1,
  "oidc": true,
  "os": "AzureLinux",
  "policy": "cilium",
  "power": "Running",
  "state": "Succeeded",
  "tier": "Free",
  "workloadIdentity": true
}
Role                                         Scope
-------------------------------------------  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
Azure Kubernetes Service RBAC Admin          Microsoft.ContainerService/managedClusters/aks-voice-azure/namespaces/voice
Cognitive Services OpenAI User               Microsoft.CognitiveServices/accounts/oai-voice-azure-e5cw8
AcrPull                                      Microsoft.ContainerRegistry/registries/acrvoiceazuree5cw8
Azure Kubernetes Service RBAC Cluster Admin  Microsoft.ContainerService/managedClusters/aks-voice-azure
Cognitive Services OpenAI User               Microsoft.CognitiveServices/accounts/oai-voice-azure-e5cw8
```
]633;E;echo;675f9b5c-ef13-48cb-82f1-3317e4c399a1]633;C
## deploy-chart: images, helm test, network flows
```
OK   az signed in as ffef284a…
OK   chat_deployment: gpt-5.4-mini
OK   cluster: aks-voice-azure
OK   gateway_client_id: c59e053c-0b36-4248-8749-a3c8a28d8d0e
OK   namespace: voice
OK   openai_endpoint: https://oai-voice-azure-e5cw8.openai.azure.com/openai/v1/
OK   registry: acrvoiceazuree5cw8.azurecr.io
OK   registry_name: acrvoiceazuree5cw8
OK   resource_group: rg-voice-azure
OK   az signed in as ffef284a…
OK   images of ci.yml run 44657470638 (main @ f55dcee40009)
OK   acrvoiceazuree5cw8.azurecr.io/voice-stt@sha256:d2753203268e78d6244de28245aa257b31a8badca2a1a67b86334767bd5c026d (sha-f55dcee40009)
OK   acrvoiceazuree5cw8.azurecr.io/voice-tts@sha256:a3794128a49127ef125a01e2edea0555aa895963a5d2513fa45c1972961bf1d8 (sha-f55dcee40009)
OK   acrvoiceazuree5cw8.azurecr.io/voice-gateway@sha256:36a81684f548f287f1871212f3a2e6a5ccd4711802e531100414361bbe83808d (sha-f55dcee40009)
OK   acrvoiceazuree5cw8.azurecr.io/voice-models@sha256:ec44a27ef36138bb527e7614b3ab5a21b237583dfaf458ca724286cd2b0a236c (sha-f55dcee40009)
OK   az signed in as ffef284a…
NAME                             STATUS   ROLES    AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                    KERNEL-VERSION             CONTAINER-RUNTIME
NAME: voice
NAMESPACE: voice
NAME                          READY   STATUS      RESTARTS   AGE
pod/gateway-968f6cc8c-t7bfh   1/1     Running     0          55s
pod/models-29ce0a6a-dg7k7     0/1     Completed   0          53s
pod/stt-777bcdfb8d-l8hhw      1/1     Running     0          55s
pod/tts-55f68fc69c-sxr2g      1/1     Running     0          55s
NAME                        STATUS     COMPLETIONS   DURATION   AGE
job.batch/models-29ce0a6a   Complete   1/1           46s        54s
NAME                           STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/models   Bound    pvc-e85a7652-86c5-46ef-baa1-2190c489bf41   1Gi        RWO            default        <unset>                 58s
NAME: voice
NAMESPACE: voice
asked:    ما هي عاصمة مملكة البحرين؟
heard:    ما هي عاصمة مملكة البحر
answered: إذا كنت تقصد مملكة البحرين فعاصمتها المنامة.
timings:  {'stt': 1.48, 'chat': 2.99, 'tts': 0.14, 'total': 4.61}
PASS status 200
PASS heard something
PASS answered something
PASS answer audio is a WAV
OK   gateway            -> stt        expected open   seen open
OK   gateway            -> tts        expected open   seen open
OK   gateway            -> outside    expected closed seen closed
OK   gateway            -> kube-api   expected closed seen closed
OK   gateway            -> model host expected closed seen closed
OK   gateway            -> entra      expected open   seen open
OK   gateway            -> chat host  expected open   seen open
OK   stt                -> tts        expected closed seen closed
OK   stt                -> gateway    expected closed seen closed
OK   stt                -> outside    expected closed seen closed
OK   stt                -> kube-api   expected closed seen closed
OK   stt                -> model host expected closed seen closed
OK   stt                -> entra      expected closed seen closed
OK   stt                -> chat host  expected closed seen closed
OK   tts                -> stt        expected closed seen closed
OK   tts                -> gateway    expected closed seen closed
OK   tts                -> outside    expected closed seen closed
OK   tts                -> kube-api   expected closed seen closed
OK   tts                -> model host expected closed seen closed
OK   tts                -> entra      expected closed seen closed
OK   tts                -> chat host  expected closed seen closed
OK   models (job)       -> stt        expected closed seen closed
OK   models (job)       -> tts        expected closed seen closed
OK   models (job)       -> gateway    expected closed seen closed
OK   models (job)       -> outside    expected closed seen closed
OK   models (job)       -> kube-api   expected closed seen closed
OK   models (job)       -> model host expected open   seen open
OK   models (job)       -> entra      expected closed seen closed
OK   models (job)       -> chat host  expected closed seen closed
OK   test (helm test)   -> stt        expected closed seen closed
OK   test (helm test)   -> tts        expected open   seen open
OK   test (helm test)   -> gateway    expected open   seen open
OK   test (helm test)   -> outside    expected closed seen closed
OK   test (helm test)   -> kube-api   expected closed seen closed
OK   test (helm test)   -> model host expected closed seen closed
OK   test (helm test)   -> entra      expected closed seen closed
OK   test (helm test)   -> chat host  expected closed seen closed
OK   loadtest           -> stt        expected open   seen open
OK   loadtest           -> tts        expected open   seen open
OK   loadtest           -> gateway    expected closed seen closed
OK   loadtest           -> outside    expected closed seen closed
OK   loadtest           -> kube-api   expected closed seen closed
OK   loadtest           -> model host expected closed seen closed
OK   loadtest           -> entra      expected closed seen closed
OK   loadtest           -> chat host  expected closed seen closed
OK   unknown pod        -> stt        expected closed seen closed
OK   unknown pod        -> tts        expected closed seen closed
OK   unknown pod        -> gateway    expected closed seen closed
OK   unknown pod        -> outside    expected closed seen closed
OK   unknown pod        -> kube-api   expected closed seen closed
OK   unknown pod        -> model host expected closed seen closed
OK   unknown pod        -> entra      expected closed seen closed
OK   unknown pod        -> chat host  expected closed seen closed
53/53 flows as expected
```

## The node after helm upgrade (D42)
```
Allocated resources:
  (Total limits may be over 100 percent, i.e., overcommitted.)
  Resource           Requests      Limits
  --------           --------      ------
  cpu                4162m (53%)   9992m (127%)
  memory             3180Mi (23%)  15958304Ki (114%)
  ephemeral-storage  0 (0%)        0 (0%)
  hugepages-1Gi      0 (0%)        0 (0%)
  hugepages-2Mi      0 (0%)        0 (0%)
Events:
```

## Pods by digest
```
gateway-968f6cc8c-t7bfh	acrvoiceazuree5cw8.azurecr.io/voice-gateway@sha256:36a81684f548f287f1871212f3a2e6a5ccd4711802e531100414361bbe83808d
models-29ce0a6a-dg7k7	acrvoiceazuree5cw8.azurecr.io/voice-models@sha256:ec44a27ef36138bb527e7614b3ab5a21b237583dfaf458ca724286cd2b0a236c
stt-777bcdfb8d-l8hhw	acrvoiceazuree5cw8.azurecr.io/voice-stt@sha256:d2753203268e78d6244de28245aa257b31a8badca2a1a67b86334767bd5c026d
tts-55f68fc69c-sxr2g	acrvoiceazuree5cw8.azurecr.io/voice-tts@sha256:a3794128a49127ef125a01e2edea0555aa895963a5d2513fa45c1972961bf1d8
voice-test-turn	acrvoiceazuree5cw8.azurecr.io/voice-gateway@sha256:36a81684f548f287f1871212f3a2e6a5ccd4711802e531100414361bbe83808d
```
]633;E;echo;675f9b5c-ef13-48cb-82f1-3317e4c399a1]633;C
## Destroy
```
[1mPlan:[0m [0m0 to add, 0 to change, 16 to destroy.
[36;1m  terraform show -no-color tfplan | grep -E '^  # |^Plan:|^No changes' | sed "s/${ARM_SUBSCRIPTION_ID}/***/g"[0m
Apply complete! Resources: 0 added, 0 changed, 16 destroyed.[0m
OK   az signed in as ffef284a…
OK   rg-voice-azure deleted
OK   rg-voice-azure-nodes deleted
rg-voice-azure exists: false
rg-voice-azure-nodes exists: false
soft-deleted OpenAI accounts: 0
state resources: 0
role assignments left: 0
tagged resources left: 0
destroyed, checks done: 2026-11-20T03:40:39Z
```

## Notes (typed from the screen during the session)
```
browser turn: <your question> | heard: <ok/wrong> | answer: <ok/wrong> | total <n> s
turns: total p90 3.34 s (M5 9.71), stt p90 1.36 (M5 2.80), chat p90 1.9 (M5 5.57), tts p90 0.26 (M5 0.95)
hpa ok calls per 15 s window (t ok): 15 10 30 11 45 10 60 11 75 12 90 17 105 17 120 16 135 20 150 15 165 14 180 16 195 17 210 19 225 17 240 17 255 4 hpa reading: <one replica ≈ n calls/15 s, two ≈ m calls/15 s: helped / didn't>
```
