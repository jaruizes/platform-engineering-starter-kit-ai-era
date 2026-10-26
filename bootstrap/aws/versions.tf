terraform {
  required_version = ">= 1.8"

  # Kept between demos with the CA and the tokens (gitignored). One person
  # runs the demo, so a local state is enough.
  backend "local" {
    path = ".state/terraform.tfstate"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.59, < 7.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

# Credentials and region come from the environment: AWS_ACCESS_KEY_ID,
# AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (if temporary) and AWS_REGION.
provider "aws" {
  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "opentofu"
    }
  }
}
