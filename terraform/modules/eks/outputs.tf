output "cluster_name" {
  value       = aws_eks_cluster.eks.name
  description = "The name of the EKS cluster"
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.eks.endpoint
  description = "The endpoint of the EKS cluster API"
}

output "cluster_certificate_authority_data" {
  value       = aws_eks_cluster.eks.certificate_authority[0].data
  sensitive   = true
  description = "Base64 encoded certificate data required to communicate with the cluster"
}

output "node_group_name" {
  value       = aws_eks_node_group.example.node_group_name
  description = "The name of the EKS node group"
}

output "node_group_status" {
  value       = aws_eks_node_group.example.status
  description = "Status of the EKS node group"
}

