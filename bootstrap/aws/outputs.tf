output "cluster_name" {
  value = module.eks.cluster_name
}

output "public_host" {
  description = "Where people and agents reach the platform."
  value       = aws_lb.platform.dns_name
}

output "image_registry" {
  description = "Where make aws-up pushes the images."
  value       = split("/", aws_ecr_repository.images["portal"].repository_url)[0]
}

output "image_repository_prefix" {
  value = var.name
}

output "service_image_repository" {
  description = "Where the pipelines push the images of the services."
  value       = aws_ecr_repository.images["services"].repository_url
}

output "image_platform" {
  description = "Platform of the images, from the architecture of the nodes."
  value       = startswith(var.node_ami_type, "AL2023_ARM") ? "linux/arm64" : "linux/amd64"
}
