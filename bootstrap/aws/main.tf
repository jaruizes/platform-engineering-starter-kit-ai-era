# The platform on AWS: a VPC, an EKS cluster that runs the control plane and
# the portal, a registry for their images, and one Application Load Balancer
# with HTTPS in front of them. Created and destroyed for each demo with
# make aws-up and make aws-down.

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  vpc_cidr = "10.0.0.0/16"
  azs      = slice(data.aws_availability_zones.available.names, 0, 2)

  # The same ports as on a laptop. The load balancer sends each one to the
  # NodePort of its service (see the manifests in mcp-server/deploy,
  # git-server and portal/deploy).
  services = {
    portal  = { port = 7007, node_port = 30007, health = "/.backstage/health/v1/readiness" }
    console = { port = 8080, node_port = 30080, health = "/" }
    mcp     = { port = 8081, node_port = 30081, health = "/healthz" }
    git     = { port = 3000, node_port = 30300, health = "/api/healthz" }
    argocd  = { port = 8082, node_port = 30082, health = "/healthz" }
  }
}

################################################################################
# Network
################################################################################

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.7"

  name = var.name
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 4, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 48)]

  # One NAT gateway is enough for a demo.
  enable_nat_gateway = true
  single_nat_gateway = true
}

################################################################################
# Kubernetes
################################################################################

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.29"

  name               = var.name
  kubernetes_version = var.kubernetes_version

  # kubectl and helm from the allowed addresses only.
  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.allowed_cidrs
  # Whoever runs make aws-up administers the cluster.
  enable_cluster_creator_admin_permissions = true
  # Pods get AWS permissions with EKS Pod Identity, not IRSA.
  enable_irsa = false

  addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = { before_compute = true }
    eks-pod-identity-agent = { before_compute = true }
    # Volumes for the Git server and the databases of the capabilities.
    # Its controller gets AWS permissions with Pod Identity: the nodes only
    # let pods reach the instance metadata with a hop limit of 1, so the
    # role of the nodes is out of its reach.
    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    platform = {
      instance_types = var.node_instance_types
      ami_type       = var.node_ami_type
      min_size       = var.node_count
      max_size       = var.node_count + 1
      desired_size   = var.node_count
      disk_size      = 50
    }
  }

  node_security_group_additional_rules = {
    load_balancer = {
      description              = "From the load balancer to the NodePorts"
      from_port                = 30000
      to_port                  = 32767
      source_security_group_id = aws_security_group.load_balancer.id
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name = "${var.name}-ebs-csi"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

################################################################################
# Images
################################################################################

resource "aws_ecr_repository" "images" {
  # The platform's own images, and the images the pipelines build for the
  # services (one repository, a tag per service and commit).
  for_each = toset(["platform-mcp", "portal", "ci-runner", "services"])

  name                 = "${var.name}/${each.key}"
  image_tag_mutability = "MUTABLE"
  # make aws-down removes them with their images.
  force_delete = true
}

# The pipeline runner pushes the service images, with EKS Pod Identity.
resource "aws_iam_role" "ci_runner" {
  name = "${var.name}-ci-runner"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy" "ci_runner" {
  name = "push-service-images"
  role = aws_iam_role.ci_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage",
        ]
        Resource = aws_ecr_repository.images["services"].arn
      },
    ]
  })
}

resource "aws_eks_pod_identity_association" "ci_runner" {
  cluster_name    = module.eks.cluster_name
  namespace       = "platform-system"
  service_account = "platform-ci-runner"
  role_arn        = aws_iam_role.ci_runner.arn
}

################################################################################
# Load balancer, with a certificate from the kit's own CA
################################################################################

resource "aws_security_group" "load_balancer" {
  name        = "${var.name}-load-balancer"
  description = "Access to the platform from the allowed addresses"
  vpc_id      = module.vpc.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "allowed" {
  for_each = {
    for pair in setproduct(keys(local.services), var.allowed_cidrs) :
    "${pair[0]}-${pair[1]}" => { port = local.services[pair[0]].port, cidr = pair[1] }
  }

  security_group_id = aws_security_group.load_balancer.id
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
  cidr_ipv4         = each.value.cidr
}

# The portal reaches the Git server at its public address, as the browser
# does, so the NAT gateway of the cluster is allowed too.
resource "aws_vpc_security_group_ingress_rule" "cluster" {
  for_each = local.services

  security_group_id = aws_security_group.load_balancer.id
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
  cidr_ipv4         = "${module.vpc.nat_public_ips[0]}/32"
}

resource "aws_vpc_security_group_egress_rule" "load_balancer" {
  security_group_id = aws_security_group.load_balancer.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_lb" "platform" {
  name               = substr(var.name, 0, 32)
  load_balancer_type = "application"
  subnets            = module.vpc.public_subnets
  security_groups    = [aws_security_group.load_balancer.id]
  # MCP keeps connections open (server-sent events).
  idle_timeout = 3600
}

resource "tls_private_key" "load_balancer" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_cert_request" "load_balancer" {
  private_key_pem = tls_private_key.load_balancer.private_key_pem
  dns_names       = [aws_lb.platform.dns_name]

  subject {
    common_name  = var.name
    organization = "Platform Starter Kit"
  }
}

resource "tls_locally_signed_cert" "load_balancer" {
  cert_request_pem   = tls_cert_request.load_balancer.cert_request_pem
  ca_private_key_pem = var.ca_key_pem
  ca_cert_pem        = var.ca_cert_pem

  validity_period_hours = 24 * 90
  allowed_uses          = ["digital_signature", "key_encipherment", "server_auth"]
}

resource "aws_acm_certificate" "load_balancer" {
  private_key       = tls_private_key.load_balancer.private_key_pem
  certificate_body  = tls_locally_signed_cert.load_balancer.cert_pem
  certificate_chain = var.ca_cert_pem
}

resource "aws_lb_target_group" "services" {
  for_each = local.services

  name        = substr("${var.name}-${each.key}", 0, 32)
  port        = each.value.node_port
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = module.vpc.vpc_id

  health_check {
    path    = each.value.health
    matcher = "200-399"
  }
}

resource "aws_autoscaling_attachment" "services" {
  for_each = local.services

  autoscaling_group_name = module.eks.eks_managed_node_groups_autoscaling_group_names[0]
  lb_target_group_arn    = aws_lb_target_group.services[each.key].arn
}

resource "aws_lb_listener" "services" {
  for_each = local.services

  load_balancer_arn = aws_lb.platform.arn
  port              = each.value.port
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.load_balancer.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services[each.key].arn
  }
}
