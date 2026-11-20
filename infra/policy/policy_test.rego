# Run: conftest verify --policy infra/policy/
# A minimal plan with one compliant resource of each type passes; each test breaks one property.
package main

import rego.v1

ws := "/subscriptions/s/resourceGroups/rg-slz-platform/providers/Microsoft.OperationalInsights/workspaces/log-slz-platform"

role(guid) := sprintf("/subscriptions/s/providers/Microsoft.Authorization/roleDefinitions/%s", [guid])

rc(module, type, name, after) := {
	"address": sprintf("%s.%s.%s", [module, type, name]),
	"module_address": module,
	"type": type,
	"name": name,
	"change": {"actions": ["create"], "after": after},
}

diag(module, logs) := rc(module, "azurerm_monitor_diagnostic_setting", "d", {"log_analytics_workspace_id": ws, "enabled_log": logs})

all_logs := [{"category": "", "category_group": "allLogs"}]

cluster := {
	"local_account_disabled": true,
	"role_based_access_control_enabled": true,
	"azure_active_directory_role_based_access_control": [{"azure_rbac_enabled": true, "tenant_id": "t"}],
	"oidc_issuer_enabled": true,
	"workload_identity_enabled": true,
	"run_command_enabled": false,
	"identity": [{"type": "SystemAssigned"}],
	"kubernetes_version": "1.36",
	"sku_tier": "Free",
	"default_node_pool": [{"node_count": 1, "auto_scaling_enabled": false, "vm_size": "Standard_F8als_v6"}],
	"network_profile": [{
		"network_plugin": "azure", "network_plugin_mode": "overlay", "network_data_plane": "cilium", "network_policy": "cilium",
		"advanced_networking": [{"security_enabled": true, "observability_enabled": false}],
	}],
}

good_resources := [
	rc("module.stack.module.aks[0]", "azurerm_kubernetes_cluster", "this", cluster),
	diag("module.stack.module.aks[0]", [{"category": "kube-audit-admin", "category_group": ""}, {"category": "guard", "category_group": ""}]),
	rc("module.stack.module.registry", "azurerm_container_registry", "this", {"sku": "Basic", "admin_enabled": false, "anonymous_pull_enabled": false}),
	diag("module.stack.module.registry", all_logs),
	rc("module.stack.module.openai[0]", "azurerm_cognitive_account", "this", {"local_auth_enabled": false, "custom_subdomain_name": "oai-x"}),
	rc("module.stack.module.openai[0]", "azurerm_cognitive_deployment", "chat", {"sku": [{"name": "GlobalStandard", "capacity": 50}]}),
	diag("module.stack.module.openai[0]", all_logs),
	rc("module.stack", "azurerm_federated_identity_credential", "gateway", {"subject": "system:serviceaccount:voice:gateway", "audience": ["api://AzureADTokenExchange"]}),
	rc("module.stack", "azurerm_role_assignment", "service", {"role_definition_id": role("7f951dda-4ed3-4680-a7ca-43fe172d538d"), "principal_type": "ServicePrincipal"}),
	rc("module.stack", "azurerm_role_assignment", "operator", {"role_definition_id": role("3498e952-d568-435e-9b2c-8d77e338d7f7"), "principal_type": "User"}),
]

plan_of(resources) := {
	"resource_changes": resources,
	"output_changes": {"summary": {"after": {"chart_settings": {"registry": "acr.azurecr.io"}}}},
}

good := plan_of(good_resources)

# Replace one value in the `after` of the resource at index i (path: "a/b/0/c").
patched(i, path, value) := plan_of(array.concat(
	array.concat(array.slice(good_resources, 0, i), [json.patch(good_resources[i], [{"op": "add", "path": sprintf("/change/after/%s", [path]), "value": value}])]),
	array.slice(good_resources, i + 1, count(good_resources)),
))

without(i) := plan_of([r | some j, r in good_resources; j != i])

test_good_plan_passes if {
	count(deny) == 0 with input as good
}

test_local_accounts_fail if {
	count(deny) == 1 with input as patched(0, "local_account_disabled", false)
}

test_kubernetes_rbac_without_azure_rbac_fails if {
	count(deny) == 1 with input as patched(0, "azure_active_directory_role_based_access_control/0/azure_rbac_enabled", false)
}

test_no_workload_identity_fails if {
	count(deny) == 1 with input as patched(0, "workload_identity_enabled", false)
}

test_service_principal_fails if {
	count(deny) == 1 with input as patched(0, "service_principal", [{"client_id": "x"}])
}

test_run_command_fails if {
	count(deny) == 1 with input as patched(0, "run_command_enabled", true)
}

test_kubenet_or_calico_fails if {
	count(deny) == 1 with input as patched(0, "network_profile/0/network_policy", "calico")
}

test_no_fqdn_security_fails if {
	count(deny) == 1 with input as patched(0, "network_profile/0/advanced_networking/0/security_enabled", false)
}

test_floating_version_fails if {
	count(deny) == 1 with input as patched(0, "kubernetes_version", null)
}

test_localdns_version_fails if {
	count(deny) == 1 with input as patched(0, "kubernetes_version", "1.37")
}

test_paid_tier_fails if {
	count(deny) == 1 with input as patched(0, "sku_tier", "Standard")
}

test_autoscaler_fails if {
	count(deny) == 1 with input as patched(0, "default_node_pool/0/auto_scaling_enabled", true)
}

test_big_node_fails if {
	count(deny) == 1 with input as patched(0, "default_node_pool/0/vm_size", "Standard_D32s_v5")
}

test_second_pool_fails if {
	count(deny) == 1 with input as plan_of(array.concat(good_resources, [rc("module.stack", "azurerm_kubernetes_cluster_node_pool", "user", {"vm_size": "Standard_F8als_v6"})]))
}

test_full_audit_log_fails if {
	count(deny) == 1 with input as patched(1, "enabled_log/0/category", "kube-audit")
}

test_premium_registry_fails if {
	count(deny) == 1 with input as patched(2, "sku", "Premium")
}

test_registry_admin_user_fails if {
	count(deny) == 1 with input as patched(2, "admin_enabled", true)
}

test_openai_keys_fail if {
	count(deny) == 1 with input as patched(4, "local_auth_enabled", true)
}

test_openai_without_subdomain_fails if {
	count(deny) == 1 with input as patched(4, "custom_subdomain_name", null)
}

test_provisioned_deployment_fails if {
	count(deny) == 1 with input as patched(5, "sku", [{"name": "GlobalProvisionedManaged", "capacity": 15}])
}

test_missing_openai_diagnostics_fail if {
	count(deny) == 1 with input as without(6)
}

test_diagnostics_elsewhere_fail if {
	count(deny) == 1 with input as patched(3, "log_analytics_workspace_id", "/subscriptions/s/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/other")
}

test_federated_credential_for_another_account_fails if {
	count(deny) == 1 with input as patched(7, "subject", "system:serviceaccount:voice:default")
}

test_owner_role_fails if {
	count(deny) == 1 with input as patched(8, "role_definition_id", role("8e3af657-a8ff-443c-a75c-2fe8c4bcb635"))
}

test_cluster_admin_for_a_user_fails if {
	count(deny) == 1 with input as patched(9, "role_definition_id", role("b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b"))
}

test_subscription_scope_fails if {
	count(deny) == 1 with input as patched(8, "scope", "/subscriptions/s")
}

test_missing_chart_settings_fails if {
	count(deny) == 1 with input as {"resource_changes": good_resources, "output_changes": {"summary": {"after": {}}}}
}

test_registry_logs_without_all_logs_fail if {
	count(deny) == 1 with input as patched(3, "enabled_log", [{"category": "ContainerRegistryLoginEvents", "category_group": ""}])
}
