# The cluster's image registry (D38): created and destroyed with the stack. gateway and models are imported from
# GHCR by digest (az acr import keeps the digest), stt and tts are pushed from the tested CI artifact; the nodes pull
# with the kubelet identity (AcrPull). No admin user, no anonymous pull: Entra ID only.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
  }
}

resource "azurerm_container_registry" "this" {
  #checkov:skip=CKV_AZURE_139:Basic has no network rules or private endpoints; access is Entra-only (admin user off, no anonymous pull)
  #checkov:skip=CKV_AZURE_163:Defender vulnerability scanning is billed per image; the images are scanned by Trivy in CI (D22)
  #checkov:skip=CKV_AZURE_164:Content trust needs Premium; images are pinned by digest instead (D38)
  #checkov:skip=CKV_AZURE_165:Geo-replication needs Premium; a registry that lives for one session
  #checkov:skip=CKV_AZURE_166:Quarantine needs Premium; only CI's tested images go in (D38)
  #checkov:skip=CKV_AZURE_167:Retention policy needs Premium; the registry is destroyed with the stack
  #checkov:skip=CKV_AZURE_233:Zone redundancy needs Premium
  #checkov:skip=CKV_AZURE_237:Dedicated data endpoints need Premium
  name                          = var.name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "Basic"
  admin_enabled                 = false
  anonymous_pull_enabled        = false
  public_network_access_enabled = true # Basic: no other option
  tags                          = var.tags
}

resource "azurerm_monitor_diagnostic_setting" "registry" {
  count                      = var.diagnostics_enabled ? 1 : 0
  name                       = "diag-to-law"
  target_resource_id         = azurerm_container_registry.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs" # logins and repository events (push, pull, delete)
  }
}
