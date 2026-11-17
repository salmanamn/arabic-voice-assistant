# The stt autoscaler under load (M5, D28)

2026-11-17 22:40 UTC, `scripts/hpa_demo.sh`: the chart's load test (`loadtest.enabled=true`) against
`stt`, CPU request 3, target 60 %, replicas 1–2.

The HPA, as `kubectl get hpa stt --watch` printed it (one line per change):
```
NAME   REFERENCE        TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
stt    Deployment/stt   cpu: 0%/60%   1         2         1          5h52m
stt    Deployment/stt   cpu: 0%/60%   1         2         1          5h52m
stt    Deployment/stt   cpu: 4%/60%   1         2         1          5h53m
stt    Deployment/stt   cpu: 77%/60%   1         2         1          5h54m
stt    Deployment/stt   cpu: 77%/60%   1         2         2          5h54m
stt    Deployment/stt   cpu: 94%/60%   1         2         2          5h55m
stt    Deployment/stt   cpu: 67%/60%   1         2         2          5h56m
stt    Deployment/stt   cpu: 67%/60%   1         2         2          5h57m
stt    Deployment/stt   cpu: 6%/60%    1         2         2          5h58m
stt    Deployment/stt   cpu: 0%/60%    1         2         2          5h59m
stt    Deployment/stt   cpu: 0%/60%    1         2         2          6h
stt    Deployment/stt   cpu: 0%/60%    1         2         1          6h
```

Rescale events:
```
2026-11-17T22:34:20Z   New size: 2; reason: cpu resource utilization (percentage of request) above target
2026-11-17T22:40:14Z   New size: 1; reason: All metrics below target
```

The load test (calls completed per 15 s window, `503 busy`, other errors, median time per call):
```
4 workers for 240 s against stt, 272428 bytes of audio per call
t=   15 s  ok   0  busy   0  error   0  p50  0.00 s
t=   30 s  ok   0  busy   0  error   0  p50  0.00 s
t=   45 s  ok   0  busy   0  error   0  p50  0.00 s
t=   60 s  ok   3  busy   0  error   0  p50 55.38 s
t=   75 s  ok   6  busy   0  error   0  p50 10.85 s
t=   90 s  ok   6  busy   0  error   0  p50  9.46 s
t=  105 s  ok   2  busy   0  error   0  p50 11.09 s
t=  120 s  ok   2  busy   0  error   0  p50 30.37 s
t=  135 s  ok   3  busy   0  error   0  p50 30.70 s
t=  150 s  ok   1  busy   0  error   0  p50 18.14 s
t=  165 s  ok   0  busy   0  error   0  p50  0.00 s
t=  181 s  ok   0  busy   0  error   0  p50  0.00 s
t=  196 s  ok   0  busy   0  error   0  p50  0.00 s
t=  211 s  ok   0  busy   0  error   0  p50  0.00 s
t=  226 s  ok   0  busy   0  error   0  p50  0.00 s
t=  241 s  ok   5  busy   0  error   0  p50 103.22 s
t=  256 s  ok   3  busy   0  error   0  p50 10.96 s
t=  271 s  ok   1  busy   0  error   0  p50 18.67 s
done
```
