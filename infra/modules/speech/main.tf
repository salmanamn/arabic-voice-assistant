# Azure AI Speech for the optional comparison with faster-whisper and Piper (M9, D59): one account, Entra ID only.
# Local (key) auth off, so the gateway identity's Cognitive Services Speech User role is the way in; the custom
# subdomain is what Entra ID tokens need. Same shape as the openai module, without deployments.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
  }
}

resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_134:Public endpoint: the gateway reaches it by name through the cluster's egress filter (D44); Entra-only access
  #checkov:skip=CKV2_AZURE_22:CMK not used for a disposable lab account; Microsoft-managed keys
  #checkov:skip=CKV_AZURE_247:Outbound is restricted with an empty allowlist: stricter than the check, which wants at least one FQDN
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  kind                = "SpeechServices"
  sku_name            = "S0" # pay per use: cents for a few dozen turns; F0 is one per subscription

  custom_subdomain_name = var.name # required for Entra ID tokens

  local_auth_enabled                 = false # no keys (D59)
  public_network_access_enabled      = true
  outbound_network_access_restricted = true # the service itself may call nothing
  fqdns                              = []

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_monitor_diagnostic_setting" "account" {
  count                      = var.diagnostics_enabled ? 1 : 0
  name                       = "diag-to-law"
  target_resource_id         = azurerm_cognitive_account.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }
}
