variable "subscription_id" {
  description = "Lab subscription (set in gitignored terraform.tfvars; CI: secret AZURE_SUBSCRIPTION_ID)"
  type        = string
}

variable "location" {
  description = "Must offer the node size and the chat model (M7 Step 0)"
  type        = string
  default     = "uaenorth"
}

variable "operator_object_id" {
  description = "Your Entra object id (az ad signed-in-user show --query id -o tsv); empty = no operator roles (D46)"
  type        = string
  default     = ""
}

variable "speech_enabled" {
  description = "The optional Azure AI Speech account (D59). CI: deploy.yml input speech (ci-deploy.sh apply --speech)"
  type        = bool
  default     = false
}

variable "deployer_object_id" {
  description = "Principal id of id-slz-apply (CI variable APPLY_PRINCIPAL_ID): installs the chart (D46)"
  type        = string
  default     = ""
}

module "stack" {
  source   = "../../modules/stack"
  name     = "voice-azure"
  location = var.location

  # Project 1 platform workspace. ID built from names: the data source would list its shared keys.
  log_analytics_workspace_id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-slz-platform/providers/Microsoft.OperationalInsights/workspaces/log-slz-platform"

  # components: the defaults (everything) on real Azure; Azure AI Speech only for the comparison evening (D59).
  components = {
    speech = var.speech_enabled
  }
  operator_object_id = var.operator_object_id
  deployer_object_id = var.deployer_object_id

  tags = {
    project    = "arabic-voice-assistant"
    managed_by = "terraform"
    env        = "azure-lab"
  }
}

output "summary" {
  value = module.stack
}
