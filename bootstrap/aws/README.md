# The platform on AWS

The same platform as `make up`, but on Amazon EKS: the control plane (Crossplane, Kyverno, Golden Paths, capabilities), the platform MCP server, the console, the Git server and the portal. The demo then needs only a browser and an internet connection, not a laptop with 8 GB for Docker.

It is meant to be **created for a demo and destroyed after it**: `make aws-up` a few days before, `make aws-down` when you are done.

```
                       allowed addresses only (ALLOWED_CIDRS)
                                     │ HTTPS (the kit's own CA)
                       ┌─────────────▼──────────────┐
                       │ Application Load Balancer   │  :7007 portal  :8080 console
                       └─────────────┬──────────────┘  :8081 MCP     :3000 Git server
                                     │ NodePorts
┌──────── VPC ───────────────────────▼──────────────────────────────────┐
│  EKS (2 × m7g.large, Graviton)                                        │
│  Crossplane · Kyverno · Golden Paths · capabilities                   │
│  platform MCP server · console · Gitea · Backstage                    │
└──────────────────────────────────────────── NAT gateway ──────────────┘
ECR: the images of the MCP server and the portal, built on your computer
```

## Before the first time

- An AWS account where you can create a VPC, EKS, IAM roles, ECR, load balancers and ACM certificates.
- On your computer: [OpenTofu](https://opentofu.org) 1.8+ (or Terraform), the AWS CLI v2, `kubectl`, `helm`, Docker with `buildx`, `openssl` and `curl`.
- The nodes are Graviton (arm64), so on an Apple Silicon Mac the images build natively. On an Intel computer, Docker builds them through emulation (slower), or use Intel nodes: `TF_VAR_node_instance_types='["m7i.large"]' TF_VAR_node_ami_type=AL2023_x86_64_STANDARD`.

## Create it

The AWS credentials go in environment variables, nothing else is read:

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...      # only for temporary credentials
export AWS_REGION=eu-west-1       # the default

make aws-up                       # about 30 minutes
```

Only your current public IP can reach the platform and the Kubernetes API. To add the address of the room where you give the demo, run it again with every address you need (everything else already exists, so it is much quicker):

```bash
ALLOWED_CIDRS=203.0.113.10/32,198.51.100.0/24 make aws-up
```

At the end it prints the URLs, which are the name AWS gives the load balancer with each port (`https://platform-starter-kit-123456.eu-west-1.elb.amazonaws.com:7007`), and three commands:

1. **Trust the CA of the demo**, once, so your browser shows no warning. The CA is created the first time and kept in `bootstrap/aws/.state`, so it stays the same demo after demo. Other people's browsers will show a warning they can accept.
2. **Connect Claude Code** to the two MCP servers on AWS, with their tokens. They are added with local scope, so they replace the ones of `.mcp.json` in this folder until `make aws-down`. Start Claude Code with `NODE_EXTRA_CA_CERTS=bootstrap/aws/.state/ca.pem claude` so it trusts the CA.
3. **Let git trust the CA** to clone the repositories the portal and the agents create.

After that, `kubectl` points to the EKS cluster (context `platform-starter-kit-aws`, which needs the same AWS variables in your shell), and the demo is the same as on a laptop: [demo/README.md](../../demo/README.md), with `make demo-developer`, `make demo-agent`, `make demo-reset` and `make status`.

## Delete it

```bash
make aws-down                     # about 15 minutes
```

It deletes the volumes the cluster created (Git server, databases of the capabilities) and then everything OpenTofu created, images included. The CA and the tokens stay in `bootstrap/aws/.state` for the next demo; delete that folder to start from scratch.

## Cost

While it is up, about **0.35 USD per hour** in `eu-west-1`: the EKS control plane (0.10), two m7g.large nodes (0.18), the NAT gateway (0.05) and the load balancer (0.02), plus a few cents for volumes and traffic. Destroyed between demos, it costs nothing.

## Security

- **Only the allowed addresses** reach the load balancer and the Kubernetes API.
- **HTTPS** with a certificate signed by the kit's own CA: there is no domain to get a public certificate for.
- **The platform MCP server requires a token** on AWS (it is open on a laptop). The tokens of both MCP servers are random, created once and kept in `bootstrap/aws/.state`.
- **No login yet**: the portal still signs everyone in as the guest Ana, and the console has no login. The allowed addresses are what protects them. A real login (Keycloak, for people and for agents) is the next step.
- The AWS credentials are only used on your computer, by OpenTofu and the AWS CLI. Nothing in the cluster has them.

## How it works

- [`main.tf`](main.tf): the VPC (two zones, one NAT gateway), EKS with a managed node group and the EBS CSI driver, ECR, and the load balancer with one HTTPS listener per port, sending traffic to the NodePorts of the services. The load balancer certificate is signed with the CA and imported into ACM.
- [`up.sh`](up.sh): creates the CA and the tokens the first time, runs OpenTofu, connects `kubectl`, logs in to ECR and runs [`bootstrap/install.sh`](../install.sh), the same installation as `make up`, with the public address, the registry and the tokens.
- The manifests and the portal configuration use the local addresses (`http://localhost:<port>`). The installer and the portal start script ([`portal/docker-entrypoint.sh`](../../portal/docker-entrypoint.sh)) rewrite them to the load balancer address, keeping each port. The portal reaches the Git server at that address too, as the browser does.
- The OpenTofu state is local, in `bootstrap/aws/.state`: one person runs the demo.
