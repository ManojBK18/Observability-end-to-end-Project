variable "cluster_name" {
  type        = string
  description = "Name of the EKS cluster."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for the EKS cluster."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the EKS node group."
}
