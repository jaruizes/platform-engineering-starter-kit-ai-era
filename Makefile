.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash

help: ## Show the available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Create the local platform (k3d, Crossplane, Kyverno, MCP server, console, portal)
	@bootstrap/local/up.sh

down: ## Delete the local platform
	@bootstrap/local/down.sh

demo-developer: ## Act 1: a developer requests an environment and deploys a service
	kubectl apply -f demo/developer/environment.yaml
	kubectl wait environments.platform.starterkit.dev/payments-dev --for=condition=Ready --timeout=120s
	kubectl apply -f demo/developer/service.yaml
	kubectl get environments.platform.starterkit.dev,apps.platform.starterkit.dev -A

demo-agent: ## Act 2 without an AI agent: a scripted agent talks to the MCP server
	kubectl -n platform-system exec deploy/platform-mcp -- python -m platform_mcp.simulate_agent

demo-reset: ## Back to a clean state before the next demo
	@demo/reset.sh

status: ## Show environments, services and pending approvals
	@kubectl get environments.platform.starterkit.dev
	@kubectl get apps.platform.starterkit.dev -A
	@kubectl -n platform-system get configmaps -l platform.starterkit.dev/approval-request \
	  -L platform.starterkit.dev/approval-status

capability: ## Check a platform capability, e.g. make capability NAME=postgres-database
	@capabilities/tools/check.sh $(NAME)

capabilities: ## List the platform capabilities installed in the cluster
	@kubectl get xrd -l platform.starterkit.dev/capability \
	  -L platform.starterkit.dev/capability

test: ## Run the unit tests of the MCP server, console and capability tools
	cd mcp-server && python -m pytest -q tests
	python -m pytest -q capabilities/tools/tests

.PHONY: help up down demo-developer demo-agent demo-reset status capability capabilities test
