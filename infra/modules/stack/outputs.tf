output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "registry" {
  value = {
    name         = module.registry.name
    login_server = module.registry.login_server
  }
}

output "gateway_identity" {
  value = {
    client_id    = azurerm_user_assigned_identity.gateway.client_id
    principal_id = azurerm_user_assigned_identity.gateway.principal_id
  }
}

output "cluster_name" {
  value = try(module.aks[0].name, null)
}

output "openai_endpoint" {
  value = try(module.openai[0].base_url, null)
}

# What scripts/aks-deploy.sh needs to install the chart (no secrets: names, endpoints, a client id).
output "chart_settings" {
  value = {
    resource_group     = azurerm_resource_group.this.name
    cluster            = try(module.aks[0].name, "")
    registry           = module.registry.login_server
    registry_name      = module.registry.name
    openai_endpoint    = try(module.openai[0].base_url, "")
    chat_deployment    = try(module.openai[0].chat_deployment, "")
    gateway_client_id  = azurerm_user_assigned_identity.gateway.client_id
    namespace          = var.namespace
    speech_resource_id = try(module.speech[0].account_id, "") # Azure AI Speech (D59): empty without components.speech
    speech_region      = try(module.speech[0].region, "")
  }
}
