"""NetworkPolicy check on the cluster (M5, D29): every flow a turn needs is open, and a sample of others is closed.

uv run python scripts/check_netpol.py [--namespace voice] [--outside 1.1.1.1:443] [--evidence FILE.md]
uv run python scripts/check_netpol.py --egress fqdn --chat-host <account>.openai.azure.com    (AKS, D44)
    [--speech-host uaenorth.stt.speech.microsoft.com --speech-host uaenorth.tts.speech.microsoft.com]  (D59)

Connects from inside the pods (kubectl exec) to the Services by cluster IP, so a closed DNS port does not hide an
open one, and to one address outside the cluster (--outside: a public address on 443). With --egress cidr (minikube,
k3s) that address stands in for a model host and the download jobs reach it. With --egress fqdn (Cilium) nothing
reaches it, and three named hosts are checked instead: the model host (huggingface.co), the chat endpoint and
Entra ID; only the download jobs reach the first, only the gateway the other two (and the Azure AI Speech hosts,
--speech-host, when the release has azureSpeech). Ollama is left out when the
release has none (Azure OpenAI). The download jobs and the test pods are not running at check time, so the script
starts short-lived probe pods with their labels (and one with a label no policy knows). Each line: from, to,
expected, seen. Exit 1 when any line differs from what is expected.
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


def probe_pod(namespace: str, name: str, component: str, image: str, instance: str, fqdn: bool = False) -> str:
    """A pod that sleeps, with the labels of `component` and the restricted security settings; returns its name.
    With name-based egress it resolves like the chart's pods do (ndots 1, D44)."""
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
                    "command": ["python", "-c", "import time; time.sleep(1800)"],
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
    if fqdn:
        spec["spec"]["dnsConfig"] = {"options": [{"name": "ndots", "value": "1"}]}
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


def kube_api_address(namespace: str) -> str:
    """The API server's cluster IP. A role scoped to one namespace can't read Services in `default` (the operator
    on AKS, D46): then ask a pod, which has it in KUBERNETES_SERVICE_HOST whether or not it mounts a token."""
    address = kubectl("default", "get", "svc", "kubernetes", "-o", "jsonpath={.spec.clusterIP}", check=False)
    if address:
        return address
    ask = "import os; print(os.environ['KUBERNETES_SERVICE_HOST'])"
    return kubectl(namespace, "exec", "deploy/gateway", "-c", "gateway", "--", "python", "-c", ask)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--namespace", default="voice")
    parser.add_argument("--release", default="voice")
    parser.add_argument("--outside", default="1.1.1.1:443", help="an address outside the cluster, host:port")
    parser.add_argument("--egress", choices=("cidr", "fqdn"), default="cidr", help="the chart's network.egress")
    parser.add_argument("--model-host", default="huggingface.co:443", help="fqdn: a model host, host:port")
    parser.add_argument("--chat-host", help="fqdn with Azure OpenAI: the endpoint's host name (port 443)")
    parser.add_argument("--entra-host", default="login.microsoftonline.com:443", help="fqdn: Entra ID, host:port")
    parser.add_argument(
        "--speech-host", action="append", default=[], help="fqdn with azureSpeech: an Azure AI Speech host (repeat)"
    )
    parser.add_argument("--evidence", type=Path, help="also write the table as Markdown to this file")
    args = parser.parse_args()
    ns = args.namespace
    outside_host, outside_port = args.outside.rsplit(":", 1)

    services = kubectl(ns, "get", "svc", "-o", "jsonpath={.items[*].metadata.name}").split()
    ollama = "ollama" in services
    ip = {
        name: kubectl(ns, "get", "svc", name, "-o", "jsonpath={.spec.clusterIP}")
        for name in ("stt", "tts", "gateway", "ollama")
        if name in services
    }
    targets = {
        "stt": (ip["stt"], 8000),
        "tts": (ip["tts"], 8000),
        "gateway": (ip["gateway"], 8080),
        **({"ollama": (ip["ollama"], 11434)} if ollama else {}),
        "outside": (outside_host, int(outside_port)),
        "kube-api": (kube_api_address(ns), 443),
    }
    named = {"model host": args.model_host, "entra": args.entra_host}
    if args.chat_host:
        named["chat host"] = f"{args.chat_host}:443"
    speech = {f"speech {i}": f"{host}:443" for i, host in enumerate(args.speech_host, start=1)}
    named.update(speech)
    if args.egress == "fqdn":
        for name, hostport in named.items():
            host, port = hostport.rsplit(":", 1)
            targets[name] = (host, int(port))
    image = kubectl(ns, "get", "deploy", "gateway", "-o", "jsonpath={.spec.template.spec.containers[0].image}")
    fqdn = args.egress == "fqdn"
    probes = {
        "models (job)": probe_pod(ns, "netpol-probe-models", "models", image, args.release, fqdn),
        "test (helm test)": probe_pod(ns, "netpol-probe-test", "test", image, args.release, fqdn),
        "loadtest": probe_pod(ns, "netpol-probe-loadtest", "loadtest", image, args.release, fqdn),
        "unknown pod": probe_pod(ns, "netpol-probe-unknown", "unknown", image, args.release, fqdn),
    }
    for pod in probes.values():
        kubectl(ns, "wait", "--for=condition=Ready", f"pod/{pod}", "--timeout=120s")
    time.sleep(3)  # policies for a new pod are programmed a moment after it is Ready

    # (from, (pod, container, bash), to, expected)
    sources = {
        "gateway": ("deploy/gateway", "gateway", False),
        "stt": ("deploy/stt", "stt", False),
        "tts": ("deploy/tts", "tts", False),
        **({"ollama": ("deploy/ollama", "ollama", True)} if ollama else {}),
        **{name: (pod, None, False) for name, pod in probes.items()},
    }
    expected_open = {
        ("gateway", "stt"),
        ("gateway", "tts"),
        ("gateway", "ollama"),
        ("test (helm test)", "gateway"),
        ("test (helm test)", "tts"),
        ("loadtest", "stt"),
        ("loadtest", "tts"),
    }
    if args.egress == "cidr":
        expected_open.add(("models (job)", "outside"))  # public addresses on 443 (D29)
    else:  # by name (D44): the address is closed for everyone; each named host for its one client
        expected_open |= {("models (job)", "model host"), ("gateway", "chat host"), ("gateway", "entra")}
        expected_open |= {("gateway", name) for name in speech}  # Azure AI Speech: the gateway only (D59)
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
                (
                    source,
                    f"{target} ({host}:{port})" if target in ("outside", "kube-api", *named) else target,
                    want,
                    seen,
                    ok,
                )
            )
            print(f"{'OK  ' if ok else 'FAIL'} {source:18} -> {target:10} expected {want:6} seen {seen}", flush=True)

    for pod in probes.values():
        kubectl(ns, "delete", "pod", pod, "--wait=false")
    print(f"{len(rows) - wrong}/{len(rows)} flows as expected")
    if args.evidence:
        lines = [
            f"# NetworkPolicy check (egress {args.egress})",
            "",
            f"Namespace `{ns}`; `scripts/check_netpol.py --egress {args.egress} --outside {args.outside}`.",
            "Connections from inside each pod",
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
