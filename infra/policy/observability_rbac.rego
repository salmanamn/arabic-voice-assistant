# Diagnostics to log-slz-platform for every resource with resource logs (D47), and a closed list of roles (D46).
package main

import rego.v1

# --- Diagnostics ---

monitored := {"azurerm_kubernetes_cluster", "azurerm_container_registry", "azurerm_cognitive_account"}

diag_modules := {object.get(rc, "module_address", "") | some rc in resources("azurerm_monitor_diagnostic_setting")}

deny contains msg if {
	some type in monitored
	some rc in resources(type)
	not object.get(rc, "module_address", "") in diag_modules
	msg := sprintf("%s: no diagnostic setting in %s", [rc.address, object.get(rc, "module_address", "root")])
}

deny contains msg if {
	some rc in resources("azurerm_monitor_diagnostic_setting")
	not is_platform_workspace(rc.change.after.log_analytics_workspace_id)
	msg := sprintf("%s: diagnostics must go to log-slz-platform", [rc.address])
}

log_categories(rc) := {l.category | some l in rc.change.after.enabled_log; l.category != ""}

log_groups(rc) := {l.category_group | some l in rc.change.after.enabled_log; l.category_group != ""}

cluster_diagnostics(rc) if contains(object.get(rc, "module_address", ""), ".module.aks")

# The cluster: Kubernetes API writes and Entra ID sign-ins, never the full audit log (reads too: GBs a day).
deny contains msg if {
	some rc in resources("azurerm_monitor_diagnostic_setting")
	cluster_diagnostics(rc)
	not {"kube-audit-admin", "guard"} == log_categories(rc)
	msg := sprintf("%s: the cluster logs kube-audit-admin and guard, nothing else (D47)", [rc.address])
}

deny contains msg if {
	some rc in resources("azurerm_monitor_diagnostic_setting")
	not cluster_diagnostics(rc)
	not "allLogs" in log_groups(rc)
	msg := sprintf("%s: enable category group allLogs", [rc.address])
}

# --- RBAC ---

role_names := {
	"7f951dda-4ed3-4680-a7ca-43fe172d538d": "AcrPull",
	"5e0bd9bd-7b93-4f28-af87-19fc36ad61bd": "Cognitive Services OpenAI User",
	"b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b": "Azure Kubernetes Service RBAC Cluster Admin",
	"3498e952-d568-435e-9b2c-8d77e338d7f7": "Azure Kubernetes Service RBAC Admin",
}

# The roles a human (the operator) may get: namespace admin, and the chat model from the laptop.
operator_roles := {"3498e952-d568-435e-9b2c-8d77e338d7f7", "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"}

role_guid(rc) := guid if {
	parts := split(rc.change.after.role_definition_id, "/")
	guid := parts[count(parts) - 1]
}

deny contains msg if {
	some rc in resources("azurerm_role_assignment")
	not role_names[role_guid(rc)]
	msg := sprintf("%s: role %v is not on the allowlist (D46)", [rc.address, object.get(rc.change.after, "role_definition_id", "<by name>")])
}

deny contains msg if {
	some rc in resources("azurerm_role_assignment")
	not principal_allowed(rc)
	msg := sprintf("%s: roles go to managed identities (ServicePrincipal); a User only gets namespace admin or OpenAI user", [rc.address])
}

principal_allowed(rc) if rc.change.after.principal_type == "ServicePrincipal"

principal_allowed(rc) if {
	rc.change.after.principal_type == "User"
	role_guid(rc) in operator_roles
}

# A scope known at plan time must be a resource, never a subscription or resource group.
deny contains msg if {
	some rc in resources("azurerm_role_assignment")
	scope := rc.change.after.scope
	is_string(scope)
	regex.match(`^/subscriptions/[^/]+(/resourceGroups/[^/]+)?/?$`, scope)
	msg := sprintf("%s: scope %s is too broad", [rc.address, scope])
}

# --- what scripts/aks-deploy.sh reads ---

deny contains "output summary.chart_settings missing: the chart deploy can't find the registry, endpoint and identity" if {
	not input.output_changes.summary.after.chart_settings
}
