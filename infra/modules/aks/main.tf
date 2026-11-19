# The cluster (D41): Entra ID sign-in with Azure RBAC for Kubernetes and no local accounts, so every kubectl call
# is a Microsoft Entra identity with an Azure role; the OIDC issuer and workload identity for the gateway (D45);
# Azure CNI overlay with the Cilium dataplane and Advanced Container Networking security, which enforces both the
# chart's NetworkPolicies and its name-based CiliumNetworkPolicies (D44). One node, no autoscaler (D42, D43).
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
  }
}

resource "azurerm_kubernetes_cluster" "this" {
  #checkov:skip=CKV_AZURE_4:No Container Insights agent: control-plane logs go to log-slz-platform by diagnostic setting; pod logs through kubectl (D47)
  #checkov:skip=CKV_AZURE_6:No authorized IP ranges: GitHub-hosted runners have no fixed addresses; every call needs Entra ID and an Azure role (D41)
  #checkov:skip=CKV_AZURE_115:Public API server for the same reason (no self-hosted runner in a VNet yet, Project 1 D14)
  #checkov:skip=CKV_AZURE_116:Azure Policy add-on (Gatekeeper) is Project 7's subject; the chart is checked by Conftest in CI and PSS at admission
  #checkov:skip=CKV_AZURE_117:Disk encryption set (CMK) not used for a node that lives a few hours; platform-managed keys
  #checkov:skip=CKV_AZURE_170:Free control-plane tier: no uptime SLA needed for a lab session (D50)
  #checkov:skip=CKV_AZURE_172:No Key Vault secrets provider: the stack has no secrets (workload identity, D45)
  #checkov:skip=CKV_AZURE_226:Ephemeral OS disks: the F*as_v6 sizes have no local disk to hold one (D42)
  #checkov:skip=CKV_AZURE_227:Host encryption needs the EncryptionAtHost subscription feature; not registered in the lab
  #checkov:skip=CKV_AZURE_232:One node pool on purpose: the speech volume is ReadWriteOnce (D43), so system and app pods share the node
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.name
  kubernetes_version  = var.kubernetes_version
  sku_tier            = "Free"
  node_resource_group = "${var.resource_group_name}-nodes"

  # Entra ID only (D41): no client certificate users, no listClusterAdminCredential.
  local_account_disabled            = false
  role_based_access_control_enabled = true
  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = var.tenant_id
  }

  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  run_command_enabled       = false # no `az aks command invoke` path next to kubectl
  azure_policy_enabled      = false

  automatic_upgrade_channel = "patch"
  node_os_upgrade_channel   = "NodeImage"

  identity {
    type = "SystemAssigned" # control plane; AKS creates the kubelet identity in the node resource group
  }

  default_node_pool {
    name                         = "system"
    vm_size                      = var.node_size
    node_count                   = 1
    auto_scaling_enabled         = false
    os_sku                       = "AzureLinux"
    os_disk_type                 = "Managed"
    os_disk_size_gb              = 64
    max_pods                     = 110
    only_critical_addons_enabled = false # one pool for the cluster's pods and ours (D43)
    temporary_name_for_rotation  = "rotate"

    upgrade_settings {
      max_surge = "1"
    }
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_data_plane  = "cilium"
    network_policy      = "cilium"
    load_balancer_sku   = "standard"
    outbound_type       = "loadBalancer"

    advanced_networking {
      security_enabled      = true  # FQDN filtering in CiliumNetworkPolicy (D44)
      observability_enabled = false # Hubble metrics: not needed, and cost the same per node
    }
  }

  storage_profile {
    disk_driver_enabled         = true # the speech models volume (Azure Disk, ReadWriteOnce)
    file_driver_enabled         = false
    blob_driver_enabled         = false
    snapshot_controller_enabled = false
  }

  tags = var.tags
}

resource "azurerm_monitor_diagnostic_setting" "cluster" {
  count                          = var.diagnostics_enabled ? 1 : 0
  name                           = "diag-to-law"
  target_resource_id             = azurerm_kubernetes_cluster.this.id
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  log_analytics_destination_type = "Dedicated" # AKSAudit*, AKSControlPlane tables

  # Writes and deletes on the Kubernetes API (no get/list/watch) and Entra ID sign-ins to the API server: what a
  # security review needs, at a fraction of kube-audit's volume (D47).
  enabled_log {
    category = "kube-audit-admin"
  }

  enabled_log {
    category = "guard"
  }
}
