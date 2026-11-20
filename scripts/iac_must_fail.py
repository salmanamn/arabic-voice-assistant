#!/usr/bin/env python3
"""IaC must fail: break one property of a real plan at a time and require the Conftest gate to reject it (D48).

The input is `terraform show -json` of the full-stack plan (infra/envs/local, -var full_stack=true). The unmodified
plan must pass; every mutation must produce at least one `deny`. A mutation whose target is missing from the plan
is STALE (update it together with the Terraform). Stdlib only; needs conftest on PATH.

Usage: python3 scripts/iac_must_fail.py <plan.json> [--policy infra/policy] [--list]
"""

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_OTHER = "/subscriptions/x/resourceGroups/rg-x/providers/Microsoft.OperationalInsights/workspaces/law-x"
OWNER = "8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
AKS_RBAC_CLUSTER_ADMIN = "b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b"


@dataclass(frozen=True)
class Mutation:
    name: str
    target: str  # resource type (its first instance), "<address part>" in angle brackets, or "<plan>"
    apply: Callable[[dict], None]  # changes rc["change"]["after"] (or the whole plan, for "<plan>")


def setter(path: str, value) -> Callable[[dict], None]:
    """Set after[a][b][0][c] for path "a.b.0.c"."""

    def run(after: dict) -> None:
        *parents, last = path.split(".")
        node = after
        for key in parents:
            node = node[int(key)] if key.isdigit() else node[key]
        node[int(last) if last.isdigit() else last] = value

    return run


def role_to(guid: str) -> Callable[[dict], None]:
    def run(after: dict) -> None:
        after["role_definition_id"] = after["role_definition_id"].rsplit("/", 1)[0] + "/" + guid

    return run


def cluster_logs_everything(after: dict) -> None:
    after["enabled_log"] = [{"category": "kube-audit", "category_group": "", "retention_policy": []}]


def drop(type_: str, address_part: str) -> Callable[[dict], None]:
    def run(plan: dict) -> None:
        before = len(plan["resource_changes"])
        plan["resource_changes"] = [
            rc for rc in plan["resource_changes"] if not (rc["type"] == type_ and address_part in rc["address"])
        ]
        if len(plan["resource_changes"]) == before:
            raise LookupError(f"{type_} in {address_part}")

    return run


def add_node_pool(plan: dict) -> None:
    pool = {
        "address": "module.stack.module.aks[0].azurerm_kubernetes_cluster_node_pool.user",
        "module_address": "module.stack.module.aks[0]",
        "type": "azurerm_kubernetes_cluster_node_pool",
        "name": "user",
        "change": {"actions": ["create"], "after": {"vm_size": "Standard_F8als_v6", "node_count": 1}},
    }
    plan["resource_changes"].append(pool)


def openai_subdomain_removed(plan: dict) -> None:
    """As if custom_subdomain_name were deleted from the module: null and no longer 'known after apply'."""
    for rc in plan["resource_changes"]:
        if rc["type"] == "azurerm_cognitive_account" and rc["change"]["after"] is not None:
            rc["change"]["after"]["custom_subdomain_name"] = None
            rc["change"].get("after_unknown", {}).pop("custom_subdomain_name", None)
            return
    raise LookupError("azurerm_cognitive_account")


def chart_settings_removed(plan: dict) -> None:
    after = plan["output_changes"]["summary"]["after"]
    if "chart_settings" not in after:
        raise LookupError("output summary.chart_settings")
    del after["chart_settings"]


MUTATIONS = [
    Mutation("cluster-local-accounts", "azurerm_kubernetes_cluster", setter("local_account_disabled", False)),
    Mutation(
        "cluster-kubernetes-rbac-only",
        "azurerm_kubernetes_cluster",
        setter("azure_active_directory_role_based_access_control.0.azure_rbac_enabled", False),
    ),
    Mutation("cluster-no-workload-identity", "azurerm_kubernetes_cluster", setter("workload_identity_enabled", False)),
    Mutation("cluster-run-command", "azurerm_kubernetes_cluster", setter("run_command_enabled", True)),
    Mutation("cluster-calico", "azurerm_kubernetes_cluster", setter("network_profile.0.network_policy", "calico")),
    Mutation(
        "cluster-no-fqdn-filtering",
        "azurerm_kubernetes_cluster",
        setter("network_profile.0.advanced_networking.0.security_enabled", False),
    ),
    Mutation("cluster-floating-version", "azurerm_kubernetes_cluster", setter("kubernetes_version", None)),
    Mutation("cluster-localdns-version", "azurerm_kubernetes_cluster", setter("kubernetes_version", "1.37")),
    Mutation("cluster-paid-tier", "azurerm_kubernetes_cluster", setter("sku_tier", "Standard")),
    Mutation(
        "cluster-autoscaler", "azurerm_kubernetes_cluster", setter("default_node_pool.0.auto_scaling_enabled", True)
    ),
    Mutation(
        "cluster-big-node", "azurerm_kubernetes_cluster", setter("default_node_pool.0.vm_size", "Standard_D32s_v5")
    ),
    Mutation("cluster-second-pool", "<plan>", add_node_pool),
    Mutation("cluster-full-audit-log", "<module.aks[0].azurerm_monitor_diagnostic_setting>", cluster_logs_everything),
    Mutation("registry-admin-user", "azurerm_container_registry", setter("admin_enabled", True)),
    Mutation("registry-premium", "azurerm_container_registry", setter("sku", "Premium")),
    Mutation("openai-api-keys", "azurerm_cognitive_account", setter("local_auth_enabled", True)),
    Mutation("openai-no-subdomain", "<plan>", openai_subdomain_removed),
    Mutation(
        "openai-provisioned-throughput",
        "azurerm_cognitive_deployment",
        setter("sku.0.name", "GlobalProvisionedManaged"),
    ),
    Mutation(
        "identity-for-default-account",
        "azurerm_federated_identity_credential",
        setter("subject", "system:serviceaccount:voice:default"),
    ),
    Mutation("role-owner", "azurerm_role_assignment", role_to(OWNER)),
    Mutation("operator-cluster-admin", "<azurerm_role_assignment.operator>", role_to(AKS_RBAC_CLUSTER_ADMIN)),
    Mutation("role-to-user", "<azurerm_role_assignment.service>", setter("principal_type", "User")),
    Mutation(
        "diagnostics-other-workspace",
        "azurerm_monitor_diagnostic_setting",
        setter("log_analytics_workspace_id", WORKSPACE_OTHER),
    ),
    Mutation("diagnostics-missing", "<plan>", drop("azurerm_monitor_diagnostic_setting", ".module.openai[0].")),
    Mutation("chart-settings-missing", "<plan>", chart_settings_removed),
    # --- the optional Azure AI Speech account (D59) ---
    Mutation("speech-api-keys", "<module.speech[0].azurerm_cognitive_account>", setter("local_auth_enabled", True)),
    Mutation("speech-multi-service-kind", "<module.speech[0].azurerm_cognitive_account>", setter("kind", "AIServices")),
    Mutation(
        "speech-outbound-open",
        "<module.speech[0].azurerm_cognitive_account>",
        setter("outbound_network_access_restricted", False),
    ),
    Mutation("speech-role-to-user", '<service["gateway_speech"]>', setter("principal_type", "User")),
]


def conftest(plan: dict, policy: Path) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(plan, fh)
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv
            ["conftest", "test", "--no-color", "--policy", str(policy), fh.name],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        Path(fh.name).unlink()
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    fails = [line.split(" - main - ", 1)[-1] for line in lines if line.startswith("FAIL")]
    if fails:
        return proc.returncode, fails[0]
    return proc.returncode, lines[-1] if lines else proc.stderr.strip()[-200:]


def mutate(plan: dict, m: Mutation) -> dict:
    out = copy.deepcopy(plan)
    if m.target == "<plan>":
        m.apply(out)
        return out
    by_address = m.target.startswith("<")
    for rc in out["resource_changes"]:
        hit = m.target.strip("<>") in rc["address"] if by_address else rc["type"] == m.target
        if hit and rc["change"]["after"] is not None:
            m.apply(rc["change"]["after"])
            return out
    raise LookupError(m.target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path, nargs="?")
    parser.add_argument("--policy", type=Path, default=ROOT / "infra" / "policy")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list or not args.plan:
        for m in MUTATIONS:
            print(f"{m.name:32} {m.target}")
        return 0 if args.list else 2

    plan = json.loads(args.plan.read_text())
    code, summary = conftest(plan, args.policy)
    if code != 0:
        print(f"ERROR    baseline: the unmodified plan fails the gate ({summary})")
        return 1
    print(f"OK       baseline: {summary}")

    problems = 0
    for m in MUTATIONS:
        try:
            mutated = mutate(plan, m)
        except (LookupError, KeyError, IndexError) as exc:
            print(f"STALE    {m.name:32} {exc} not in the plan; update the mutation")
            problems += 1
            continue
        code, summary = conftest(mutated, args.policy)
        if code != 0:
            print(f"DENIED   {m.name:32} {summary}")
        else:
            print(f"ALLOWED  {m.name:32} the gate passed it: add or fix a policy rule")
            problems += 1
    print(f"{len(MUTATIONS) - problems}/{len(MUTATIONS)} mutations denied")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
