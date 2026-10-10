variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "project" {
  type    = string
  default = "student-portal"
}
variable "alert_email" {
  type        = string
  description = "Email that receives alarm notifications"
}
variable "my_ip_cidr" {
  type        = string
  description = "Your public IP for SSH, e.g. 1.2.3.4/32"
}
variable "admin_key" {
  type        = string
  sensitive   = true
  description = "Secret the admin must send in the x-admin-key header to write data"
}
variable "create_vm" {
  type    = bool
  default = true
}
variable "billing_threshold_usd" {
  type    = number
  default = 5
}
