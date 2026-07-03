variable "vpc_name" {
  description = "Name of the VPC."
  type        = string
}

variable "igw_name" {
  description = "Name of the Internet Gateway."
  type        = string
}

variable "nat_name" {
  description = "Name of the NAT Gateway."
  type        = string
}

variable "nat_eip" {
  description = "Name of the NAT Gateway EIP."
  type        = string
} 