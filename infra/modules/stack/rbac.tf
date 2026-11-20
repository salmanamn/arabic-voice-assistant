# Every role the stack assigns (D46), each at the narrowest scope, by built-in role id. Nothing at resource-group
# or subscription scope. The apply identity may assign exactly these (Project 1 bootstrap ABAC list).
locals {
  role_ids = {
    acr_pull               = "7f951dda-4ed3-4680-a7ca-43fe172d538d" # AcrPull
    openai_user            = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd" # Cognitive Services OpenAI User
    aks_rbac_cluster_admin = "b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b" # Azure Kubernetes Service RBAC Cluster Admin
    aks_rbac_admin         = "3498e952-d568-435e-9b2c-8d77e338d7f7" # Azure Kubernetes Service RBAC Admin
    speech_user            = "f2dc8367-1007-4938-bd23-fe263f013447" # Cognitive Services Speech User
  }

  # Managed identities.
  service_roles = merge(
    var.components.aks ? {
      # the nodes pull our images (kubelet identity, created by AKS in the node resource group)
      kubelet_pull = { scope = module.registry.id, role = "acr_pull", principal = module.aks[0].kubelet_object_id }
    } : {},
    var.components.openai ? {
      # the gateway's chat completions with an Entra ID token (D45)
      gateway_openai = { scope = module.openai[0].account_id, role = "openai_user", principal = azurerm_user_assigned_identity.gateway.principal_id }
    } : {},
    var.components.speech ? {
      # the gateway's speech to text and text to speech on Azure AI Speech, with an Entra ID token (D59)
      gateway_speech = { scope = module.speech[0].account_id, role = "speech_user", principal = azurerm_user_assigned_identity.gateway.principal_id }
    } : {},
    var.components.aks && length(var.deployer_object_id) > 0 ? {
      # CI's apply identity installs the chart: namespace, workloads, CiliumNetworkPolicies (deploy.yml deploy-chart)
      deployer = { scope = module.aks[0].id, role = "aks_rbac_cluster_admin", principal = var.deployer_object_id }
    } : {},
  )

  # The human operator (D46): helm test, logs, port-forward and the network check in namespace voice; the chat model
  # from the laptop (scripts/eval_chat.py). Omitted when operator_object_id is empty.
  operator_roles = length(var.operator_object_id) == 0 ? {} : merge(
    var.components.aks ? {
      operator_namespace = { scope = "${module.aks[0].id}/namespaces/${var.namespace}", role = "aks_rbac_admin" }
    } : {},
    var.components.openai ? {
      operator_openai = { scope = module.openai[0].account_id, role = "openai_user" }
    } : {},
  )
}

resource "azurerm_role_assignment" "service" {
  for_each           = var.components.rbac ? local.service_roles : {}
  scope              = each.value.scope
  role_definition_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids[each.value.role]}"
  principal_id       = each.value.principal
  principal_type     = "ServicePrincipal"
  description        = "voice ${each.key}"
}

resource "azurerm_role_assignment" "operator" {
  for_each           = var.components.rbac ? local.operator_roles : {}
  scope              = each.value.scope
  role_definition_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids[each.value.role]}"
  principal_id       = var.operator_object_id
  principal_type     = "User"
  description        = "voice operator: ${each.key}"
}
