variable "full_stack" {
  description = <<-EOT
    false (default): only what floci-az 0.16.0 can create, for plan and apply (resource group, gateway identity,
    registry and its diagnostic setting).
    true: every component, for `plan` only (the CI policy gate). Never apply with true: floci-az 0.16.0's AKS
    handler stores no identity, OIDC issuer or Entra profile, it answers 404 for role assignments, and it has no
    Cognitive Services handler (D39).
  EOT
  type        = bool
  default     = false
}

data "azurerm_client_config" "current" {}

module "stack" {
  source   = "../../modules/stack"
  name     = "voice-local"
  location = "eastus"

  # Same id shape as on Azure. floci-az stores diagnostic settings without checking their destination.
  log_analytics_workspace_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/rg-slz-platform/providers/Microsoft.OperationalInsights/workspaces/log-slz-platform"

  components = {
    aks    = var.full_stack
    openai = var.full_stack
    rbac   = var.full_stack
    speech = var.full_stack # the policy gate plans the optional Speech account too (D59)
  }

  # Placeholders so the full-stack plan has every role assignment the Azure plan has (plan only).
  operator_object_id = var.full_stack ? "00000000-0000-0000-0000-00000000000a" : ""
  deployer_object_id = var.full_stack ? "00000000-0000-0000-0000-00000000000b" : ""

  tags = {
    project    = "arabic-voice-assistant"
    managed_by = "terraform"
    env        = "local"
  }
}

output "summary" {
  value = module.stack
}
