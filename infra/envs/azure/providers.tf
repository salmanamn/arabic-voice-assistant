terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  backend "azurerm" {} # values in backend.hcl (shared Project 1 state account); az CLI locally, OIDC in CI
}

# Real Azure. Identity from `az login` locally (use_cli defaults to true), GitHub OIDC in CI; subscription pinned.
# No emulator settings here: in particular NEVER skip_import_check_on_create_... (Project 1 D10).
provider "azurerm" {
  subscription_id = var.subscription_id

  # Registered by hand once (M7 Step 0): the CI identities can't register providers. azurerm only checks them.
  resource_provider_registrations = "none"
  resource_providers_to_register = [
    "Microsoft.Authorization",
    "Microsoft.CognitiveServices",
    "Microsoft.Compute",
    "Microsoft.ContainerRegistry",
    "Microsoft.ContainerService",
    "Microsoft.Insights",
    "Microsoft.ManagedIdentity",
    "Microsoft.Network",
    "Microsoft.OperationalInsights",
  ]

  features {
    resource_group {
      prevent_deletion_if_contains_resources = true # destroy fails loudly if something was created outside Terraform
    }

    cognitive_account {
      purge_soft_delete_on_destroy = true # a soft-deleted account keeps its name (and quota) for 48 h otherwise
    }
  }
}
