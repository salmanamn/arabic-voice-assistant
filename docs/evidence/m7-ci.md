# CI and the plan gate (M7)

## PR #10 (M7) checks
```
chart	pass	11s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610056	
e2e	pass	1m10s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135790490906	
iac-plan	pass	36s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610745	
apply	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010884/job/135790019182	
iac-static	pass	30s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610344	
images	pass	1m22s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610334	
lint	pass	29s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610219	
tests-must-fail	pass	1m0s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610339	
unit	pass	29s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789610358	
publish	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135791245405	
plan	pass	36s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010884/job/135789610524	
deploy-chart	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010884/job/135789613210	
pins	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44589010739/job/135789613551	
```

## Gate demo, PR #11 (closed): AKS local accounts on
```
iac-plan	fail	41s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795802755	
iac-static	fail	26s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795803043	
plan	fail	34s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755347/job/135795794241	
chart	pass	11s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795802831	
unit	pass	25s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795802148	
publish	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135797310303	
tests-must-fail	pass	1m2s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795802658	
apply	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755347/job/135796176416	
e2e	pass	1m14s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135796525749	
images	pass	1m8s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795802804	
lint	pass	26s	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795803062	
deploy-chart	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755347/job/135795796695	
pins	skipping	0	https://github.com/salmanamn/arabic-voice-assistant/actions/runs/44590755607/job/135795804471	
mergeStateStatus at the time: BLOCKED
```

## Branch protection
```
OK   lint: success (app 15368)
OK   unit: success (app 15368)
OK   tests-must-fail: success (app 15368)
OK   chart: success (app 15368)
OK   iac-static: success (app 15368)
OK   iac-plan: success (app 15368)
OK   images: success (app 15368)
OK   e2e: success (app 15368)
{"checks":["lint (app 15368)","unit (app 15368)","tests-must-fail (app 15368)","chart (app 15368)","images (app 15368)","e2e (app 15368)","iac-static (app 15368)","iac-plan (app 15368)"],"deletions":false,"enforce_admins":true,"force_pushes":false,"linear_history":true,"pr_required":true,"strict":true}
```
