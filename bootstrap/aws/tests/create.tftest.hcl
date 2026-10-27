# Checks the configuration without an AWS account: every AWS call is mocked,
# so it proves the resources fit together, not that AWS accepts them.
#   openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.pem -subj /CN=test -days 1
#   TF_VAR_ca_cert_pem="$(cat ca.pem)" TF_VAR_ca_key_pem="$(cat ca.key)" tofu test
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["eu-west-1a", "eu-west-1b", "eu-west-1c"] }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws", dns_suffix = "amazonaws.com" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012", arn = "arn:aws:iam::123456789012:user/demo" }
  }
  mock_data "aws_iam_session_context" {
    defaults = { issuer_arn = "arn:aws:iam::123456789012:user/demo" }
  }
  mock_data "aws_eks_addon_version" {
    defaults = { version = "v1.0.0-eksbuild.1" }
  }
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:eu-west-1:123456789012:loadbalancer/app/x/1", dns_name = "platform-starter-kit-1.eu-west-1.elb.amazonaws.com" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/x/1" }
  }
  mock_resource "aws_acm_certificate" {
    defaults = { arn = "arn:aws:acm:eu-west-1:123456789012:certificate/1" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/x" }
  }
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::123456789012:policy/x" }
  }
  mock_resource "aws_launch_template" {
    defaults = { id = "lt-0123456789abcdef0" }
  }
  mock_resource "aws_eks_node_group" {
    defaults = { resources = [{ autoscaling_groups = [{ name = "eks-platform-asg" }], remote_access_security_group_id = "" }], arn = "arn:aws:eks:eu-west-1:123456789012:nodegroup/x/y/z" }
  }
  mock_resource "aws_eip" {
    defaults = { public_ip = "198.51.100.1" }
  }
  mock_resource "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:eu-west-1:123456789012:key/1" }
  }
  mock_resource "aws_eks_cluster" {
    defaults = { arn = "arn:aws:eks:eu-west-1:123456789012:cluster/x", certificate_authority = [{ data = "eA==" }] }
  }
}
mock_provider "time" {}
mock_provider "null" {}
mock_provider "cloudinit" {}

variables {
  allowed_cidrs = ["203.0.113.10/32"]
}

run "create" {
  command = apply
  assert {
    condition     = length(aws_lb_listener.services) == 4
    error_message = "One HTTPS listener per service."
  }
  assert {
    condition     = alltrue([for rule in aws_vpc_security_group_ingress_rule.allowed : rule.cidr_ipv4 == "203.0.113.10/32"])
    error_message = "Only the allowed addresses reach the load balancer."
  }
  assert {
    condition     = output.image_platform == "linux/arm64"
    error_message = "Graviton nodes need arm64 images."
  }
}
