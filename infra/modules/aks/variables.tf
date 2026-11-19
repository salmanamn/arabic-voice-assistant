variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tenant_id" {
  description = "Entra tenant of the cluster's users (Azure RBAC for Kubernetes)"
  type        = string
}

variable "kubernetes_version" {
  description = "Minor version only (AKS picks the newest patch); must match deploy/namespace.yaml's PSS version"
  type        = string
}

variable "node_size" {
  type = string
}

variable "diagnostics_enabled" {
  type = bool
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "tags" {
  type = map(string)
}
