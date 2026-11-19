"""Chart must fail: apply known-bad changes to the Helm chart one at a time and require the policy to deny each one.

Each mutation weakens one property the chart promises (restricted Pod Security, no CPU limits, threads from the
CPU request, probes and a graceful stop, read-only model volumes, default-deny networking, egress only for the
download Jobs; on AKS: images by digest, egress by host name only, the workload identity on the gateway only). The
script renders a temporary copy of the chart with `helm template` and runs Conftest on it, so the working tree is
never changed. A mutation without a file changes only the values it renders with. Exit 1 when a mutation is
allowed (the policy misses it), when its anchor text is no longer in the chart (update the mutation together
with the chart), or when a clean rendering (laptop, CI or AKS values) is denied (D35).

Usage: uv run python scripts/chart_must_fail.py [--only NAME] [--list]   (needs helm and conftest on PATH)
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = "deploy/charts/voice"


AZURE = (
    "-f",
    str(ROOT / "deploy" / "azure-values.yaml"),
    "-f",
    str(ROOT / "deploy" / "policy" / "fixtures" / "azure-render.yaml"),
)


@dataclass(frozen=True)
class Mutation:
    name: str
    file: str | None  # relative to the chart; None: only `values` change
    old: str
    new: str
    denied: str  # text the denial must contain
    values: tuple[str, ...] = ()  # extra helm arguments


MUTATIONS = [
    Mutation("pod-as-root", "templates/_helpers.tpl", "  runAsNonRoot: true", "  runAsNonRoot: false", "runAsNonRoot"),
    Mutation("seccomp-unconfined", "templates/_helpers.tpl", "type: RuntimeDefault", "type: Unconfined", "seccomp"),
    Mutation(
        "privilege-escalation",
        "templates/_helpers.tpl",
        "allowPrivilegeEscalation: false",
        "allowPrivilegeEscalation: true",
        "allowPrivilegeEscalation",
    ),
    Mutation(
        "writable-root",
        "templates/_helpers.tpl",
        "readOnlyRootFilesystem: true",
        "readOnlyRootFilesystem: false",
        "readOnlyRootFilesystem",
    ),
    Mutation("capability-kept", "templates/_helpers.tpl", "drop: [ALL]", "drop: [NET_RAW]", "drop ALL"),
    Mutation(
        "token-mounted",
        "templates/_helpers.tpl",
        "automountServiceAccountToken: false",
        "automountServiceAccountToken: true",
        "automountServiceAccountToken",
    ),
    Mutation(
        "cpu-limit",
        "values.yaml",
        "    limits: { memory: 2048Mi }",
        '    limits: { memory: 2048Mi, cpu: "3" }',
        "no CPU limits",
    ),
    Mutation(
        "no-memory-limit",
        "values.yaml",
        "    limits: { memory: 256Mi } # the floor for any service (D21)",
        "    limits: {}",
        "needs limits.memory",
    ),
    Mutation(
        "threads-hard-coded",
        "templates/stt.yaml",
        "              valueFrom:\n"
        '                resourceFieldRef: { containerName: stt, resource: requests.cpu, divisor: "1" }',
        '              value: "6"',
        "STT_THREADS",
    ),
    Mutation("no-startup-probe", "templates/_helpers.tpl", "startupProbe:", "x-startupProbe:", "needs a startupProbe"),
    Mutation(
        "short-grace",
        "templates/stt.yaml",
        "terminationGracePeriodSeconds: 45",
        "terminationGracePeriodSeconds: 10",
        "preStop",
    ),
    Mutation(
        "models-writable",
        "templates/stt.yaml",
        "persistentVolumeClaim: { claimName: models, readOnly: true }",
        "persistentVolumeClaim: { claimName: models }",
        "claim models must be read-only",
    ),
    Mutation(
        "ollama-models-writable",
        "templates/ollama.yaml",
        "            - { name: models, mountPath: /models, readOnly: true }\n"
        "            - { name: scripts, mountPath: /scripts, readOnly: true }\n"
        "            - { name: tmp, mountPath: /tmp }\n      containers:",
        "            - { name: models, mountPath: /models }\n"
        "            - { name: scripts, mountPath: /scripts, readOnly: true }\n"
        "            - { name: tmp, mountPath: /tmp }\n      containers:",
        "must be mounted read-only",
    ),
    Mutation(
        "no-default-deny",
        "templates/networkpolicy.yaml",
        '  name: default-deny\n  labels: {{- include "voice.labels" . | nindent 4 }}\nspec:\n  podSelector: {}',
        '  name: default-deny\n  labels: {{- include "voice.labels" . | nindent 4 }}\nspec:\n'
        "  podSelector: { matchLabels: { none: none } }",
        "no default-deny",
    ),
    Mutation(
        "gateway-may-download",
        "templates/networkpolicy.yaml",
        "values: [models, ollama-pull] }\n  policyTypes: [Ingress, Egress]",
        "values: [models, ollama-pull, gateway] }\n  policyTypes: [Ingress, Egress]",
        "ipBlock egress only for the download Jobs",
    ),
    Mutation(
        "private-ranges-reachable",
        "values.yaml",
        "            10.0.0.0/8,\n",
        "",
        "must except the private",
    ),
    Mutation(
        "ollama-may-call-out",
        "templates/networkpolicy.yaml",
        "      ports: [{ protocol: TCP, port: 11434 }]\n---",
        "      ports: [{ protocol: TCP, port: 11434 }]\n  egress:\n    - to: [{ ipBlock: { cidr: 0.0.0.0/0 } }]\n---",
        "must have no egress at all",
    ),
    Mutation("job-unbounded", "templates/models-job.yaml", "backoffLimit: 4", "backoffLimit: 100", "backoffLimit"),
    # --- AKS (deploy/azure-values.yaml + the made-up deploy values): D38, D44, D45 ---
    Mutation(
        "azure-image-by-tag",
        None,
        "",
        "",
        "must be pulled by digest",
        (*AZURE, "--set", "images.digests.gateway="),
    ),
    Mutation(
        "any-host-by-name",
        None,
        "",
        "",
        '"*" matches every name',
        (*AZURE, "--set", "network.fqdn.modelHosts={huggingface.co,*}"),
    ),
    Mutation(
        "public-range-and-names",
        "templates/networkpolicy.yaml",
        "  {{- if not $fqdn }}\n  egress:",
        "  {{- if true }}\n  egress:",
        "no ipBlock when egress is by name",
        AZURE,
    ),
    Mutation(
        "stt-reaches-hosts",
        "templates/networkpolicy.yaml",
        "values: [models, ollama-pull] }\n  egress:",
        "values: [models, ollama-pull, stt] }\n  egress:",
        "only the download Jobs and the gateway reach hosts by name",
        AZURE,
    ),
    Mutation(
        "names-for-every-pod",
        "templates/networkpolicy.yaml",
        "  endpointSelector:\n"
        '    matchLabels: {{- include "voice.selector" (dict "root" . "component" "gateway") | nindent 6 }}',
        "  endpointSelector: {}",
        "an empty selector selects every pod",
        AZURE,
    ),
    Mutation(
        "egress-to-the-world",
        "templates/networkpolicy.yaml",
        '    {{- include "voice.fqdnEgress" (dict "root" . "hosts" .Values.network.fqdn.modelHosts',
        "    - toEntities: [world]\n"
        '    {{- include "voice.fqdnEgress" (dict "root" . "hosts" .Values.network.fqdn.modelHosts',
        "egress rules may only name hosts",
        AZURE,
    ),
    Mutation(
        "names-on-any-port",
        "templates/_helpers.tpl",
        '        - { port: "443", protocol: TCP }',
        '        - { port: "80", protocol: TCP }',
        "on port 443 only",
        AZURE,
    ),
    Mutation(
        "dns-unfiltered",
        "templates/_helpers.tpl",
        "      rules:\n        dns:\n          {{- range .dnsNames }}\n"
        '          - {{ if contains "*" . }}matchPattern{{ else }}matchName{{ end }}: {{ . | quote }}\n'
        "          {{- end }}\n",
        "",
        "toFQDNs needs a DNS rule",
        AZURE,
    ),
    Mutation(
        "tts-with-identity",
        "templates/tts.yaml",
        '      labels: {{- include "voice.selector" (dict "root" . "component" "tts") | nindent 8 }}',
        '      labels:\n        {{- include "voice.selector" (dict "root" . "component" "tts") | nindent 8 }}\n'
        '        azure.workload.identity/use: "true"',
        "only the gateway runs with a workload identity",
        AZURE,
    ),
    Mutation(
        "identity-on-another-account",
        "templates/gateway.yaml",
        "kind: ServiceAccount\nmetadata:\n  name: gateway",
        "kind: ServiceAccount\nmetadata:\n  name: tts",
        "only the gateway's service account carries a workload identity",
        AZURE,
    ),
    Mutation(
        "account-token-mounted",
        "templates/gateway.yaml",
        "automountServiceAccountToken: false",
        "automountServiceAccountToken: true",
        "automountServiceAccountToken must be false",
        AZURE,
    ),
    Mutation(
        "key-next-to-token",
        "templates/gateway.yaml",
        "            - { name: OPENAI_AUTH, value: entra }",
        "            - { name: OPENAI_AUTH, value: entra }\n            - { name: OPENAI_API_KEY, value: sk-x }",
        "there is no OPENAI_API_KEY",
        AZURE,
    ),
]


def render_and_check(chart: Path, extra: tuple[str, ...]) -> tuple[int, str]:
    rendered = subprocess.run(  # noqa: S603 (helm with fixed arguments)
        ["helm", "template", "voice", str(chart), "-n", "voice", *extra],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if rendered.returncode != 0:
        return 2, f"helm template failed: {rendered.stderr.strip()[-300:]}"
    checked = subprocess.run(  # noqa: S603
        ["conftest", "test", "--combine", "--no-color", "-p", str(ROOT / "deploy" / "policy"), "-"],  # noqa: S607
        input=rendered.stdout,
        capture_output=True,
        text=True,
        check=False,
    )
    return checked.returncode, checked.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="run a single mutation by name")
    parser.add_argument("--list", action="store_true", help="list the mutations and exit")
    args = parser.parse_args()
    mutations = [m for m in MUTATIONS if not args.only or m.name == args.only]
    if args.list or not mutations:
        for m in MUTATIONS:
            print(f"{m.name:28} {m.file or '(values only)'}")
        return 0 if args.list else 2

    with tempfile.TemporaryDirectory(prefix="chart-must-fail-") as tmp:
        chart = Path(tmp) / "voice"
        shutil.copytree(ROOT / CHART, chart)
        baselines = {
            "values.yaml": (),
            "ci-values.yaml": ("-f", str(ROOT / "deploy" / "ci-values.yaml")),
            "azure": AZURE,
        }
        for label, extra in baselines.items():
            code, out = render_and_check(chart, extra)
            if code != 0:
                print(f"ERROR    baseline ({label}) is denied:\n{out}")
                return 1
            print(f"OK       baseline ({label}): allowed")

        problems = 0
        for m in mutations:
            path = chart / m.file if m.file else None
            original = path.read_text(encoding="utf-8") if path else ""
            if path and original.count(m.old) != 1:
                print(f"STALE    {m.name:28} anchor found {original.count(m.old)}x in {m.file}; update the mutation")
                problems += 1
                continue
            if path:
                path.write_text(original.replace(m.old, m.new), encoding="utf-8")
            try:
                code, out = render_and_check(chart, m.values)
            finally:
                if path:
                    path.write_text(original, encoding="utf-8")
            if code == 1 and m.denied in out:
                print(f"DENIED   {m.name:28} ({m.denied})")
            elif code == 0:
                print(f"ALLOWED  {m.name:28} the policy lets it through: add or fix a rule")
                problems += 1
            else:
                print(f"ERROR    {m.name:28} exit {code}, expected a denial containing {m.denied!r}:\n{out[-400:]}")
                problems += 1
    print(f"{len(mutations) - problems}/{len(mutations)} mutations denied")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
