"""Terraform (infra/), the chart's Azure values and the cluster manifests must describe the same deployment (D48).

Terraform creates the cluster, the gateway's federated credential and the chat deployment; the chart runs the
gateway under a service account in a namespace with a pinned Pod Security version and calls a deployment by name.
None of that meets before an Azure session, so these tests fail when one side changes without the other.
"""

import math
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / "infra" / "modules" / "stack"
CHART = ROOT / "deploy" / "charts" / "voice"


def tf_default(variable: str) -> str:
    """Default of a variable in infra/modules/stack/variables.tf: a quoted scalar, or a field of an object default."""
    text = (STACK / "variables.tf").read_text(encoding="utf-8")
    block = re.search(rf'variable "{variable}" \{{(.*?)\n\}}', text, re.DOTALL)
    assert block, f"variable {variable} not found"
    default = re.search(r'^\s*default\s*=\s*"([^"]*)"', block.group(1), re.MULTILINE)
    assert default, f"variable {variable} has no scalar default"
    return default.group(1)


def tf_object_default(variable: str, field: str) -> str:
    text = (STACK / "variables.tf").read_text(encoding="utf-8")
    block = re.search(rf'variable "{variable}" \{{(.*?)\n\}}', text, re.DOTALL)
    assert block, f"variable {variable} not found"
    value = re.search(rf'^\s*{field}\s*=\s*"([^"]*)"', block.group(1).split("default", 1)[1], re.MULTILINE)
    assert value, f"{variable}.{field} has no default"
    return value.group(1)


def yaml_file(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_cluster_version_is_the_pod_security_version_and_the_ci_cluster_version():
    version = tf_default("kubernetes_version")
    labels = yaml_file(ROOT / "deploy" / "namespace.yaml")["metadata"]["labels"]
    assert {labels[f"pod-security.kubernetes.io/{m}-version"] for m in ("enforce", "warn", "audit")} == {f"v{version}"}
    k3s = re.search(r"^K3S_VERSION=v(\d+\.\d+)\.", (ROOT / "scripts" / "ci-tools.sh").read_text(), re.MULTILINE)
    assert k3s and k3s.group(1) == version  # e2e in CI tests the chart on the same minor as AKS


def test_federated_credential_names_the_charts_service_account():
    namespace = yaml_file(ROOT / "deploy" / "namespace.yaml")["metadata"]["name"]
    assert tf_default("namespace") == namespace
    gateway = (CHART / "templates" / "gateway.yaml").read_text(encoding="utf-8")
    account = tf_default("gateway_service_account")
    assert f"serviceAccountName: {account}\n" in gateway
    assert f"kind: ServiceAccount\nmetadata:\n  name: {account}\n" in gateway
    main = (STACK / "main.tf").read_text(encoding="utf-8")
    assert 'subject                   = "system:serviceaccount:${var.namespace}:${var.gateway_service_account}"' in main


def test_azure_values_call_the_terraform_chat_deployment():
    azure = yaml_file(ROOT / "deploy" / "azure-values.yaml")
    assert azure["azureOpenAI"]["enabled"] is True
    assert azure["azureOpenAI"]["deployment"] == tf_object_default("chat_deployment", "model")
    assert azure["azureOpenAI"]["reasoningEffort"]  # gpt-5.x rejects temperature and max_tokens (D45)
    assert azure["network"]["egress"] == "fqdn"  # the chart refuses Azure OpenAI with address-based egress


def test_two_speech_replicas_fit_the_node():
    """STT_THREADS is the CPU request rounded up (D26); both replicas' threads must have a core each (D42)."""
    azure = yaml_file(ROOT / "deploy" / "azure-values.yaml")
    cores = int(re.search(r"Standard_[A-Z](\d+)", tf_default("node_size")).group(1))
    request = azure["stt"]["resources"]["requests"]["cpu"]
    cpu = int(request[:-1]) / 1000 if request.endswith("m") else float(request)
    assert azure["stt"]["hpa"]["maxReplicas"] * math.ceil(cpu) <= cores - 1  # one core for the cluster's own pods


def test_model_host_is_allowed_by_name():
    values = yaml_file(CHART / "values.yaml")
    host = re.match(r"https://([^/]+)", values["models"]["hfEndpoint"]).group(1)
    assert host in values["network"]["fqdn"]["modelHosts"]
