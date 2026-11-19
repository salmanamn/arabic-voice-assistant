# Composition root: everything both environments deploy (D40).
# envs/local and envs/azure call only this module and differ ONLY in provider config and inputs.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    random  = { source = "hashicorp/random" }
  }
}

data "azurerm_client_config" "current" {}

# Registry and OpenAI names are global DNS names -> random suffix
resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

locals {
  suffixed = "${var.name}-${random_string.suffix.result}"
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.name}"
  location = var.location
  tags     = var.tags
}

# The gateway's identity (D45): its pods get Entra ID tokens for it through the federated credential below.
resource "azurerm_user_assigned_identity" "gateway" {
  name                = "id-${var.name}-gateway"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = var.tags
}

module "registry" {
  source                     = "../registry"
  name                       = "acr${replace(var.name, "-", "")}${random_string.suffix.result}"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  diagnostics_enabled        = var.diagnostics_enabled
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags
}

module "aks" {
  count                      = var.components.aks ? 1 : 0
  source                     = "../aks"
  name                       = "aks-${var.name}"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  kubernetes_version         = var.kubernetes_version
  node_size                  = var.node_size
  diagnostics_enabled        = var.diagnostics_enabled
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags
}

module "openai" {
  count                      = var.components.openai ? 1 : 0
  source                     = "../openai"
  name                       = "oai-${local.suffixed}"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  chat                       = var.chat_deployment
  diagnostics_enabled        = var.diagnostics_enabled
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags
}

# Workload identity (D45): Azure accepts the cluster's tokens for this one service account as the gateway identity.
resource "azurerm_federated_identity_credential" "gateway" {
  count                     = var.components.aks ? 1 : 0
  name                      = "aks-${var.name}-gateway"
  user_assigned_identity_id = azurerm_user_assigned_identity.gateway.id
  issuer                    = module.aks[0].oidc_issuer_url
  audience                  = ["api://AzureADTokenExchange"]
  subject                   = "system:serviceaccount:${var.namespace}:${var.gateway_service_account}"
}
