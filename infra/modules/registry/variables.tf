variable "name" {
  description = "Registry name (5-50 letters and digits, globally unique)"
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9]{5,50}$", var.name))
    error_message = "name: 5-50 letters and digits."
  }
}

variable "resource_group_name" {
  type = string
}

variable "location" {
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
