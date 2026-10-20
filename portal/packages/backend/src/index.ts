/*
 * Backstage backend for the Platform Starter Kit portal.
 *
 * Humans use the portal to request Golden Paths through Software Templates.
 * AI agents read context from it through MCP (catalog, Kubernetes, team
 * usage, engineering standards) and act through the platform MCP server,
 * inside the guardrails.
 */

import { createBackend } from '@backstage/backend-defaults';
import {
  catalogModulePlatform,
  scaffolderModulePlatform,
} from '@internal/backstage-plugin-platform-backend';

const backend = createBackend();

backend.add(import('@backstage/plugin-app-backend'));
backend.add(import('@backstage/plugin-proxy-backend'));

// auth: guest sign-in for the local demo
backend.add(import('@backstage/plugin-auth-backend'));
backend.add(import('@backstage/plugin-auth-backend-module-guest-provider'));

// catalog, including AI resources (skills, rules, MCP servers) and what the
// Golden Paths created in the cluster
backend.add(import('@backstage/plugin-catalog-backend'));
backend.add(
  import('@backstage/plugin-catalog-backend-module-scaffolder-entity-model'),
);
backend.add(import('@backstage/plugin-catalog-backend-module-ai-model'));
backend.add(import('@backstage/plugin-catalog-backend-module-logs'));
backend.add(catalogModulePlatform);
// services created from the Spring service template, discovered in the local
// Git server
backend.add(import('@backstage/plugin-catalog-backend-module-gitea'));

// software templates for the Golden Paths; new services are published to the
// local Git server (Gitea)
backend.add(import('@backstage/plugin-scaffolder-backend'));
backend.add(import('@backstage/plugin-scaffolder-backend-module-gitea'));
backend.add(scaffolderModulePlatform);

// techdocs: the engineering standards, built when the image is built
backend.add(import('@backstage/plugin-techdocs-backend'));

// permissions
backend.add(import('@backstage/plugin-permission-backend'));
backend.add(
  import('@backstage/plugin-permission-backend-module-allow-all-policy'),
);

// search (in memory)
backend.add(import('@backstage/plugin-search-backend'));
backend.add(import('@backstage/plugin-search-backend-module-catalog'));

// kubernetes: live status of environments and services
backend.add(import('@backstage/plugin-kubernetes-backend'));

backend.add(import('@backstage/plugin-events-backend'));
backend.add(import('@backstage/plugin-user-settings-backend'));
backend.add(import('@backstage/plugin-notifications-backend'));
backend.add(import('@backstage/plugin-signals-backend'));

// platform: agent approvals, AI-era metrics and context actions for agents
backend.add(import('@internal/backstage-plugin-platform-backend'));

// MCP: Backstage actions as tools for AI agents
backend.add(import('@backstage/plugin-mcp-actions-backend'));

backend.start();
