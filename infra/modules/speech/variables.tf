variable "name" {
  description = "Account name and custom subdomain (globally unique)"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  description = "Also the region of the Speech REST endpoints the gateway calls (<region>.stt/.tts.speech.microsoft.com)"
  type        = string
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
