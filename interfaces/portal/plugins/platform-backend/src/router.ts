import { HttpAuthService } from '@backstage/backend-plugin-api';
import { InputError, NotFoundError } from '@backstage/errors';
import express from 'express';
import Router from 'express-promise-router';
import { ConsoleClient } from './console';
import { readQualityResult } from './quality';

export async function createRouter({
  httpAuth,
  platformConsole,
  displayName,
  qualityGitUrl,
}: {
  httpAuth: HttpAuthService;
  platformConsole: ConsoleClient;
  displayName: (userEntityRef: string) => Promise<string>;
  qualityGitUrl: string;
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

  router.get('/quality/:service', async (req, res) => {
    if (!/^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$/.test(req.params.service)) {
      throw new InputError('Invalid service name');
    }
    const result = await readQualityResult(qualityGitUrl, req.params.service);
    if (!result) {
      res.status(404).json({ status: 'unknown', reason: 'No committed quality evidence found.' });
      return;
    }
    res.json(result);
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
