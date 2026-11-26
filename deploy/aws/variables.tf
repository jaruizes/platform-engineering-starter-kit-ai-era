variable "name" {
  description = "Name of the cluster and prefix of every resource."
  type        = string
  default     = "platform-starter-kit"
}

variable "kubernetes_version" {
  description = "Kubernetes version of the EKS cluster."
  type        = string
  default     = "1.34"
}

variable "node_instance_types" {
  description = "Instance types of the nodes. Graviton (arm64) by default: cheaper, and images built on an Apple Silicon Mac run natively."
  type        = list(string)
  default     = ["m7g.large"]
}

variable "node_ami_type" {
  description = "AMI type of the nodes: AL2023_ARM_64_STANDARD for Graviton, AL2023_x86_64_STANDARD for Intel or AMD."
  type        = string
  default     = "AL2023_ARM_64_STANDARD"
}

variable "node_count" {
  description = "Number of nodes. Two m7g.large (2 vCPU, 8 GiB each) run the whole platform."
  type        = number
  default     = 2
}

variable "allowed_cidrs" {
  description = "Who can reach the platform and the Kubernetes API, for example your public IP as 203.0.113.10/32."
  type        = list(string)

  validation {
    condition     = length(var.allowed_cidrs) > 0 && !contains(var.allowed_cidrs, "0.0.0.0/0")
    error_message = "List at least one CIDR, and not 0.0.0.0/0: the demo has no login yet."
  }
}

variable "ca_cert_pem" {
  description = "Certificate of the CA that signs the load balancer certificate (bootstrap/aws/up.sh creates it once)."
  type        = string
}

variable "ca_key_pem" {
  description = "Private key of that CA."
  type        = string
  sensitive   = true
}
