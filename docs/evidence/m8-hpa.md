# The stt autoscaler under load (M8 on AKS, D28, D42)

2026-11-20 03:00 UTC, `scripts/hpa_demo.sh`: the chart's load test (`loadtest.enabled=true`) against
`stt`, CPU request 2500m, target 60 %, replicas 1–2.

The HPA, as `kubectl get hpa stt --watch` printed it (one line per change):
```
NAME   REFERENCE        TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
stt    Deployment/stt   cpu: 0%/60%   1         2         1          32m
```

Rescale events:
```
2026-11-20T02:52:38Z   New size: 2; reason: cpu resource utilization (percentage of request) above target
2026-11-20T02:59:24Z   New size: 1; reason: All metrics below target
```

The load test (calls completed per 15 s window, `503 busy`, other errors, median time per call):
```
4 workers for 240 s against stt, 280108 bytes of audio per call
t=   15 s  ok  10  busy   0  error   0  p50  5.62 s
t=   30 s  ok  11  busy   0  error   0  p50  5.63 s
t=   45 s  ok  10  busy   0  error   0  p50  5.65 s
t=   60 s  ok  11  busy   0  error   0  p50  5.63 s
t=   75 s  ok  12  busy   0  error   0  p50  5.66 s
t=   90 s  ok  17  busy   0  error   0  p50  4.41 s
t=  105 s  ok  17  busy   0  error   0  p50  3.23 s
t=  120 s  ok  16  busy   0  error   0  p50  3.72 s
t=  135 s  ok  20  busy   0  error   0  p50  3.23 s
t=  150 s  ok  15  busy   0  error   0  p50  4.46 s
t=  165 s  ok  14  busy   0  error   0  p50  4.45 s
t=  180 s  ok  16  busy   0  error   0  p50  4.55 s
t=  195 s  ok  17  busy   0  error   0  p50  3.24 s
t=  210 s  ok  19  busy   0  error   0  p50  3.24 s
t=  225 s  ok  17  busy   0  error   0  p50  3.25 s
t=  240 s  ok  17  busy   0  error   0  p50  4.44 s
t=  255 s  ok   4  busy   0  error   0  p50  4.52 s
done
```
