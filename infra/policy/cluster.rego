# The cluster (D41-D44): Entra ID and Azure RBAC only, workload identity, Cilium with name-based egress, one node.
package main

import rego.v1

clusters := resources("azurerm_kubernetes_cluster")

deny contains msg if {
	some rc in clusters
	rc.change.after.local_account_disabled != true
	msg := sprintf("%s: local accounts must be disabled (Entra ID only, D41)", [rc.address])
}

deny contains msg if {
	some rc in clusters
	not azure_rbac(rc.change.after)
	msg := sprintf("%s: Entra ID integration with Azure RBAC for Kubernetes is required (D41)", [rc.address])
}

azure_rbac(a) if {
	a.role_based_access_control_enabled != false
	[aad] := a.azure_active_directory_role_based_access_control
	aad.azure_rbac_enabled == true
}

deny contains msg if {
	some rc in clusters
	not workload_identity(rc.change.after)
	msg := sprintf("%s: the OIDC issuer and workload identity are required for the gateway (D45)", [rc.address])
}

workload_identity(a) if {
	a.oidc_issuer_enabled == true
	a.workload_identity_enabled == true
}

deny contains msg if {
	some rc in clusters
	count(object.get(rc.change.after, "service_principal", [])) > 0
	msg := sprintf("%s: a managed identity, not a service principal with a secret", [rc.address])
}

deny contains msg if {
	some rc in clusters
	rc.change.after.run_command_enabled != false
	msg := sprintf("%s: run command must be off (no path around kubectl and Azure RBAC)", [rc.address])
}

deny contains msg if {
	some rc in clusters
	not cilium_fqdn(rc.change.after)
	msg := sprintf("%s: Azure CNI with the Cilium dataplane and ACNS security (FQDN policies) is required (D44)", [rc.address])
}

cilium_fqdn(a) if {
	[net] := a.network_profile
	net.network_plugin == "azure"
	net.network_data_plane == "cilium"
	net.network_policy == "cilium"
	[adv] := net.advanced_networking
	adv.security_enabled == true
}

deny contains msg if {
	some rc in clusters
	not regex.match(`^1\.[0-9]+$`, object.get(rc.change.after, "kubernetes_version", ""))
	msg := sprintf("%s: pin the Kubernetes minor version (deploy/namespace.yaml pins the Pod Security version to it)", [rc.address])
}

# --- cost and the ReadWriteOnce volume (D42, D43, D50) ---

allowed_node_sizes := {"Standard_F8als_v6", "Standard_F8as_v6"}

deny contains msg if {
	some rc in clusters
	rc.change.after.sku_tier != "Free"
	msg := sprintf("%s: Free control-plane tier for the lab (D50)", [rc.address])
}

deny contains msg if {
	some rc in clusters
	[pool] := rc.change.after.default_node_pool
	not one_fixed_node(pool)
	msg := sprintf("%s: one node, no autoscaler (the models volume is ReadWriteOnce, D43)", [rc.address])
}

one_fixed_node(pool) if {
	pool.node_count == 1
	pool.auto_scaling_enabled != true
}

deny contains msg if {
	some rc in clusters
	[pool] := rc.change.after.default_node_pool
	not pool.vm_size in allowed_node_sizes
	msg := sprintf("%s: node size %s is not one of %v (D42)", [rc.address, pool.vm_size, allowed_node_sizes])
}

deny contains msg if {
	some rc in resources("azurerm_kubernetes_cluster_node_pool")
	msg := sprintf("%s: no second node pool (D43)", [rc.address])
}

# --- registry (D38) ---

deny contains msg if {
	some rc in resources("azurerm_container_registry")
	rc.change.after.sku != "Basic"
	msg := sprintf("%s: Basic registry for the lab (D38, D50)", [rc.address])
}

deny contains msg if {
	some rc in resources("azurerm_container_registry")
	not entra_only_registry(rc.change.after)
	msg := sprintf("%s: no admin user and no anonymous pull (Entra ID only, D38)", [rc.address])
}

entra_only_registry(a) if {
	a.admin_enabled == false
	a.anonymous_pull_enabled != true
}

# --- Azure OpenAI (D45) ---

deny contains msg if {
	some rc in resources("azurerm_cognitive_account")
	rc.change.after.local_auth_enabled != false
	msg := sprintf("%s: Azure OpenAI key auth must be disabled (local_auth_enabled = false)", [rc.address])
}

deny contains msg if {
	some rc in resources("azurerm_cognitive_account")
	object.get(rc.change.after, "custom_subdomain_name", null) in {null, ""}
	object.get(rc.change, ["after_unknown", "custom_subdomain_name"], false) != true # known only after apply: fine
	msg := sprintf("%s: a custom subdomain is required for Entra ID tokens", [rc.address])
}

deny contains msg if {
	some rc in resources("azurerm_cognitive_deployment")
	some sku in rc.change.after.sku
	contains(sku.name, "Provisioned")
	msg := sprintf("%s: provisioned throughput (%s) is billed per hour whether used or not; use a Standard SKU", [rc.address, sku.name])
}

# --- workload identity (D45) ---

deny contains msg if {
	some rc in resources("azurerm_federated_identity_credential")
	not gateway_subject(rc.change.after)
	msg := sprintf("%s: the federated credential trusts only system:serviceaccount:voice:gateway with audience api://AzureADTokenExchange", [rc.address])
}

gateway_subject(a) if {
	a.subject == "system:serviceaccount:voice:gateway"
	a.audience == ["api://AzureADTokenExchange"]
}
