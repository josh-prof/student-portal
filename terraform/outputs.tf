output "api_url" {
  value = aws_apigatewayv2_api.api.api_endpoint
}
output "web_url" {
  value = var.create_vm ? "http://${aws_instance.web[0].public_ip}" : null
}
output "audit_bucket" {
  value = aws_s3_bucket.audit.bucket
}
