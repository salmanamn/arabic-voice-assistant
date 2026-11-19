variable "name" {
  description = "Name stem, e.g. voice-local or voice-azure"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,13}$", var.name))
    error_message = "name: 3-14 chars, lowercase letters/digits/hyphens, starts with a letter."
  }
}

variable "location" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "log_analytics_workspace_id" {
  description = "Central workspace for diagnostics (log-slz-platform, Project 1)"
  type        = string
}

variable "diagnostics_enabled" {
  description = "Diagnostic settings on every resource that has logs"
  type        = bool
  default     = true
}

variable "components" {
  description = "Everything is on by default. envs/local turns off what floci-az 0.16.0 can't create (D39)."
  type = object({
    aks    = optional(bool, true) # Microsoft.ContainerService (+ the gateway's federated credential)
    openai = optional(bool, true) # Microsoft.CognitiveServices accounts + deployments
    rbac   = optional(bool, true) # Microsoft.Authorization/roleAssignments
  })
  default = {}
}

variable "kubernetes_version" {
  description = "AKS minor version; deploy/namespace.yaml pins the Pod Security Standard to the same one (D41)"
  type        = string
  default     = "1.37"
}

variable "node_size" {
  description = "The one node (D42): 8 cores without SMT, 16 GiB. Check quota and offer before changing (M7 Step 0)."
  type        = string
  default     = "Standard_F8als_v6"
}

variable "namespace" {
  description = "The chart's namespace (deploy/namespace.yaml)"
  type        = string
  default     = "voice"
}

variable "gateway_service_account" {
  description = "The gateway's service account in the chart (templates/gateway.yaml)"
  type        = string
  default     = "gateway"
}

variable "chat_deployment" {
  description = "Azure OpenAI chat deployment (D45): gpt-5.4-mini 2026-03-17, Global Standard, GA (retires 2027-09-21)"
  type = object({
    model    = string
    version  = string
    sku      = string
    capacity = number
  })
  default = {
    model    = "gpt-5.4-mini"
    version  = "2026-03-17"
    sku      = "GlobalStandard"
    capacity = 50
  }
}

variable "operator_object_id" {
  description = "Entra object id of the human operator: namespace admin and OpenAI user (D46). Empty = none."
  type        = string
  default     = ""
}

variable "deployer_object_id" {
  description = "Principal id of CI's apply identity (id-slz-apply): installs the chart (D46). Empty = none."
  type        = string
  default     = ""
}
