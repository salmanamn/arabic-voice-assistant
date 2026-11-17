"""NetworkPolicy check on the cluster (M5, D29): every flow a turn needs is open, and a sample of others is closed.

uv run python scripts/check_netpol.py [--namespace voice] [--outside 1.1.1.1:443] [--evidence FILE.md]

Connects from inside the pods (kubectl exec) to the Services by cluster IP, so a closed DNS port does not hide an
open one, and to one address outside the cluster (--outside: a public address on 443, standing in for a model
host). The download jobs and the test pods are not running at check time, so the script starts short-lived probe
pods with their labels (and one with a label no policy knows). Each line: from, to, expected, seen. Exit 1 when any
line differs from what is expected.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

LABEL = "app.kubernetes.io/component"
# Python in our images; bash's /dev/tcp in Ollama's (no Python there). Prints "open" or "closed".
PY_CONNECT = (
    "import socket,sys\n"
    "try:\n socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3).close(); print('open')\n"
    "except OSError: print('closed')"
)
BASH_CONNECT = 'timeout 3 bash -c "</dev/tcp/$0/$1" 2>/dev/null && echo open || echo closed'


def kubectl(namespace: str, *args: str, check: bool = True) -> str:
    result = subprocess.run(  # noqa: S603 (kubectl with fixed arguments)
        ["kubectl", "-n", namespace, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"kubectl {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def probe_pod(namespace: str, name: str, component: str, image: str, instance: str) -> str:
    """A pod that sleeps, with the labels of `component` and the restricted security settings; returns its name."""
    spec = {
        "metadata": {
            "labels": {"app.kubernetes.io/name": "voice", "app.kubernetes.io/instance": instance, LABEL: component}
        },
        "spec": {
            "automountServiceAccountToken": False,
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 10001,
                "runAsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "probe",
                    "image": image,
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["python", "-c", "import time; time.sleep(600)"],
                    "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}, "limits": {"memory": "64Mi"}},
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                }
            ],
        },
    }
    kubectl(namespace, "delete", "pod", name, "--ignore-not-found", "--wait=true")
    kubectl(namespace, "run", name, f"--image={image}", "--restart=Never", f"--overrides={json.dumps(spec)}")
    return name


def connect(namespace: str, pod: str, container: str | None, host: str, port: int, bash: bool) -> str:
    target = ["exec", pod] + (["-c", container] if container else []) + ["--"]
    if bash:
        command = ["bash", "-c", BASH_CONNECT, host, str(port)]
    else:
        command = ["python", "-c", PY_CONNECT, host, str(port)]
    return kubectl(namespace, *target, *command, check=False) or "error"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--namespace", default="voice")
    parser.add_argument("--release", default="voice")
    parser.add_argument("--outside", default="1.1.1.1:443", help="an address outside the cluster, host:port")
    parser.add_argument("--evidence", type=Path, help="also write the table as Markdown to this file")
    args = parser.parse_args()
    ns = args.namespace
    outside_host, outside_port = args.outside.rsplit(":", 1)

    ip = {
        name: kubectl(ns, "get", "svc", name, "-o", "jsonpath={.spec.clusterIP}")
        for name in ("stt", "tts", "gateway", "ollama")
    }
    targets = {
        "stt": (ip["stt"], 8000),
        "tts": (ip["tts"], 8000),
        "gateway": (ip["gateway"], 8080),
        "ollama": (ip["ollama"], 11434),
        "outside": (outside_host, int(outside_port)),
        "kube-api": (kubectl("default", "get", "svc", "kubernetes", "-o", "jsonpath={.spec.clusterIP}"), 443),
    }
    image = kubectl(ns, "get", "deploy", "gateway", "-o", "jsonpath={.spec.template.spec.containers[0].image}")
    probes = {
        "models (job)": probe_pod(ns, "netpol-probe-models", "models", image, args.release),
        "test (helm test)": probe_pod(ns, "netpol-probe-test", "test", image, args.release),
        "loadtest": probe_pod(ns, "netpol-probe-loadtest", "loadtest", image, args.release),
        "unknown pod": probe_pod(ns, "netpol-probe-unknown", "unknown", image, args.release),
    }
    for pod in probes.values():
        kubectl(ns, "wait", "--for=condition=Ready", f"pod/{pod}", "--timeout=120s")
    time.sleep(3)  # policies for a new pod are programmed a moment after it is Ready

    # (from, (pod, container, bash), to, expected)
    sources = {
        "gateway": ("deploy/gateway", "gateway", False),
        "stt": ("deploy/stt", "stt", False),
        "tts": ("deploy/tts", "tts", False),
        "ollama": ("deploy/ollama", "ollama", True),
        **{name: (pod, None, False) for name, pod in probes.items()},
    }
    expected_open = {
        ("gateway", "stt"),
        ("gateway", "tts"),
        ("gateway", "ollama"),
        ("models (job)", "outside"),
        ("test (helm test)", "gateway"),
        ("test (helm test)", "tts"),
        ("loadtest", "stt"),
        ("loadtest", "tts"),
    }
    rows, wrong = [], 0
    for source, (pod, container, bash) in sources.items():
        for target, (host, port) in targets.items():
            if source == target:
                continue
            want = "open" if (source, target) in expected_open else "closed"
            seen = connect(ns, pod, container, host, port, bash)
            ok = seen == want
            wrong += not ok
            rows.append(
                (source, f"{target} ({host}:{port})" if target in ("outside", "kube-api") else target, want, seen, ok)
            )
            print(f"{'OK  ' if ok else 'FAIL'} {source:18} -> {target:9} expected {want:6} seen {seen}", flush=True)

    for pod in probes.values():
        kubectl(ns, "delete", "pod", pod, "--wait=false")
    print(f"{len(rows) - wrong}/{len(rows)} flows as expected")
    if args.evidence:
        lines = [
            "# NetworkPolicy check (M5)",
            "",
            f"Namespace `{ns}`; `scripts/check_netpol.py --outside {args.outside}`. Connections from inside each pod",
            "to the Services' cluster IPs; probe pods carry the labels of the jobs and the test pod.",
            "",
            "| From | To | Expected | Seen | |",
            "|---|---|---|---|---|",
        ]
        lines += [f"| {s} | {t} | {w} | {seen} | {'OK' if ok else 'FAIL'} |" for s, t, w, seen, ok in rows]
        lines += ["", f"{len(rows) - wrong}/{len(rows)} flows as expected.", ""]
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {args.evidence}")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
