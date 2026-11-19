# Azure OpenAI for the gateway (D45): one account and the chat deployment that replaces Ollama's phi4-mini.
# Entra ID only: local (key) auth off, so the gateway identity's Cognitive Services OpenAI User role is the way in.
# Same shape as ticket-triage-agent's module (its D19), without embeddings.
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
  kind                = "OpenAI"
  sku_name            = "S0"

  custom_subdomain_name = var.name # required for Entra ID tokens: https://<name>.openai.azure.com/

  local_auth_enabled                 = false # no API keys (D45)
  public_network_access_enabled      = true
  outbound_network_access_restricted = true # the service itself may call nothing
  fqdns                              = []

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_cognitive_deployment" "chat" {
  name                   = var.chat.model # the gateway sends the deployment name as `model` (CHAT_MODEL)
  cognitive_account_id   = azurerm_cognitive_account.this.id
  version_upgrade_option = "OnceCurrentVersionExpired"
  rai_policy_name        = "Microsoft.DefaultV2"

  model {
    format  = "OpenAI"
    name    = var.chat.model
    version = var.chat.version
  }

  sku {
    name     = var.chat.sku
    capacity = var.chat.capacity # thousands of tokens per minute
  }
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
