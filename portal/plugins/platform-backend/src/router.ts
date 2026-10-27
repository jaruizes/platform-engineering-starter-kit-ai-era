import { HttpAuthService } from '@backstage/backend-plugin-api';
import { InputError, NotFoundError } from '@backstage/errors';
import express from 'express';
import Router from 'express-promise-router';
import { ConsoleClient } from './console';

export async function createRouter({
  httpAuth,
  platformConsole,
  displayName,
}: {
  httpAuth: HttpAuthService;
  platformConsole: ConsoleClient;
  displayName: (userEntityRef: string) => Promise<string>;
}): Promise<express.Router> {
  const router = Router();
  router.use(express.json());

  router.get('/overview', async (_req, res) => {
    const state = await platformConsole.state();
    res.json({
      metrics: state.metrics,
      environments: state.environments,
      apps: state.apps,
      approvals: state.approvals,
      activity: state.activity.slice(0, 20),
    });
  });

  // The approver is the signed-in Backstage user, not a name typed in a form.
  router.post('/approvals/:id', async (req, res) => {
    const credentials = await httpAuth.credentials(req, { allow: ['user'] });
    const decision = req.body?.decision;
    if (decision !== 'approve' && decision !== 'reject') {
      throw new InputError('decision must be approve or reject');
    }
    const approver = await displayName(credentials.principal.userEntityRef);
    const result = await platformConsole.decide(req.params.id, decision, approver);
    if (result.status === 404) {
      throw new NotFoundError('Approval request not found');
    }
    res.status(result.status).json(result.body);
  });

  return router;
}
