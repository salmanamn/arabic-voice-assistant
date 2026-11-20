output "account_id" {
  description = "The account's ARM id: the role scope, and part of every token the Speech REST APIs take (D59)"
  value       = azurerm_cognitive_account.this.id
}

output "region" {
  value = azurerm_cognitive_account.this.location
}
