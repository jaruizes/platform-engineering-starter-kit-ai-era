import { ActionsRegistryService } from '@backstage/backend-plugin-api/alpha';
import { ConsoleClient } from './console';
import { PlatformClient, summarizeApp, summarizeEnvironment } from './kubernetes';

const TEAM_LIMIT = 3;

/**
 * Read-only context for AI agents, exposed as MCP tools by Backstage.
 * Agents read context here and act through the platform MCP server.
 */
export function registerActions(
  actionsRegistry: ActionsRegistryService,
  platform: PlatformClient,
  platformConsole: ConsoleClient,
) {
  actionsRegistry.register({
    name: 'get-team-usage',
    title: 'Get a team platform usage',
    description:
      'Returns what a team has on the platform: active environments and services, who requested ' +
      'them (human or agent), daily cost, how many of its environment slots are free and which ' +
      'agent requests are waiting for a human. Use it before asking the platform MCP server for ' +
      'a new environment.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z => z.object({ team: z.string().describe('Team name, for example checkout') }),
      output: z =>
        z.object({
          team: z.string(),
          environments: z.array(z.record(z.any())),
          services: z.array(z.record(z.any())),
          dailyCostEur: z.number(),
          freeEnvironmentSlots: z.number(),
          pendingApprovals: z.array(z.record(z.any())),
        }),
    },
    action: async ({ input }) => {
      const [envs, apps, state] = await Promise.all([
        platform.listEnvironments(),
        platform.listApps(),
        platformConsole.state().catch(() => undefined),
      ]);
      const environments = envs.map(summarizeEnvironment).filter(e => e.team === input.team);
      const names = new Set(environments.map(e => e.name));
      const services = apps.map(summarizeApp).filter(a => names.has(a.environment));
      const pendingApprovals = (state?.approvals ?? [])
        .filter(a => a.status === 'pending' && a.request.team === input.team)
        .map(a => ({ id: a.id, agent: a.agent, environment: a.request.name, reason: a.reason }));
      const dailyCostEur = environments.reduce((sum, e) => sum + e.estimatedDailyCostEur, 0);
      return {
        output: {
          team: input.team,
          environments,
          services,
          dailyCostEur: Math.round(dailyCostEur * 100) / 100,
          freeEnvironmentSlots: Math.max(0, TEAM_LIMIT - environments.length),
          pendingApprovals,
        },
      };
    },
  });

  actionsRegistry.register({
    name: 'list-pending-approvals',
    title: 'List agent requests waiting for a human',
    description:
      'Lists the agent requests that the guardrails sent to a human, with the reason and who ' +
      'decided the recent ones. Approvals are made by people in the portal, never by agents.',
    attributes: { readOnly: true, idempotent: true },
    schema: {
      input: z => z.object({}),
      output: z => z.object({ approvals: z.array(z.record(z.any())) }),
    },
    action: async () => {
      const state = await platformConsole.state();
      return {
        output: {
          approvals: state.approvals.map(a => ({
            id: a.id,
            status: a.status,
            agent: a.agent,
            environment: a.request.name,
            team: a.request.team,
            size: a.request.size,
            reason: a.reason,
            decidedBy: a.decided_by,
          })),
        },
      };
    },
  });
}
