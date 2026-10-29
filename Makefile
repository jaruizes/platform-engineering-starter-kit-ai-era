.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
PYTHON ?= python3

help: ## Show the available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Create the local platform (k3d, Crossplane, Kyverno, MCP server, console, portal)
	@bootstrap/local/up.sh

down: ## Delete the local platform
	@bootstrap/local/down.sh

aws-up: ## Create the platform on AWS for a demo (AWS credentials in environment variables)
	@bootstrap/aws/up.sh

aws-down: ## Delete the platform on AWS
	@bootstrap/aws/down.sh

demo-developer: ## Act 1: a developer requests an environment and deploys a service
	kubectl apply -f examples/scenarios/developer/environment.yaml
	kubectl wait environments.platform.starterkit.dev/payments-dev --for=condition=Ready --timeout=120s
	kubectl apply -f examples/scenarios/developer/service.yaml
	kubectl get environments.platform.starterkit.dev,apps.platform.starterkit.dev -A

demo-agent: ## Act 2 without an AI agent: a scripted agent talks to the MCP server
	kubectl -n platform-system exec deploy/platform-mcp -- python -m platform_mcp.simulate_agent

demo-reset: ## Back to a clean state before the next demo
	@examples/scenarios/reset.sh

status: ## Show environments, services and pending approvals
	@kubectl get environments.platform.starterkit.dev
	@kubectl get apps.platform.starterkit.dev -A
	@kubectl -n platform-system get configmaps -l platform.starterkit.dev/approval-request \
	  -L platform.starterkit.dev/approval-status

capability: ## Check a platform capability, e.g. make capability NAME=postgres-database
	@platform/capabilities/tools/check.sh $(NAME)

capabilities: ## List the platform capabilities installed in the cluster
	@kubectl get xrd -l platform.starterkit.dev/capability \
	  -L platform.starterkit.dev/capability

sonar-up: ## Install the optional SonarQube demo in the current cluster
	@kubectl apply -f platform/quality/sonarqube.yaml
	@kubectl -n quality rollout status deployment/sonarqube --timeout=600s
	@echo "Run: kubectl -n quality port-forward svc/sonarqube 9000:9000, then open http://localhost:9000 (initial login admin/admin)."

sonar-down: ## Remove the optional SonarQube demo and its data
	@kubectl delete -f platform/quality/sonarqube.yaml --ignore-not-found
	@kubectl delete namespace quality --ignore-not-found

demo-quality: ## Demonstrate an ArchUnit violation failing and its correction passing
	@python3 platform/quality/demo.py

test: ## Run the unit tests of the MCP server, console and capability tools
	cd interfaces/mcp && $(PYTHON) -m pytest -q tests
	$(PYTHON) -m pytest -q platform/capabilities/tools/tests
	$(PYTHON) -m pytest -q platform/quality/tests

.PHONY: help up down aws-up aws-down demo-developer demo-agent demo-reset status capability capabilities sonar-up sonar-down demo-quality test
