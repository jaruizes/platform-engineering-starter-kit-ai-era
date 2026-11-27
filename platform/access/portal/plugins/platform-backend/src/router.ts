import { HttpAuthService } from '@backstage/backend-plugin-api';
import { InputError } from '@backstage/errors';
import express from 'express';
import Router from 'express-promise-router';
import { PlatformApiClient, PlatformApiError } from './platformApi';
import { readQualityResult } from './quality';

/**
 * The header the AI Platform page sends the signed-in person's Keycloak
 * access token in (the Authorization header carries the Backstage token).
 */
export const PLATFORM_TOKEN_HEADER = 'x-platform-token';

export async function createRouter({
  httpAuth,
  api,
  qualityGitUrl,
}: {
  httpAuth: HttpAuthService;
  api: PlatformApiClient;
  qualityGitUrl: string;
}): Promise<express.Router> {
  const router = Router();
  router.use(express.json());

  // The platform API decides; the portal forwards the person's token and its answer.
  const forward = async (res: express.Response, call: () => Promise<unknown>) => {
    try {
      res.json(await call());
    } catch (error) {
      if (error instanceof PlatformApiError) {
        res.status(error.status).json({ error: { name: 'PlatformApiError', message: error.message } });
        return;
      }
      throw error;
    }
  };

  router.get('/overview', async (req, res) => {
    await httpAuth.credentials(req, { allow: ['user'] });
    await forward(res, () => api.overview(req.header(PLATFORM_TOKEN_HEADER) ?? ''));
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

  // The approver is the person whose token this is: the platform API checks
  // the approver role for the team and four eyes, not the portal.
  router.post('/approvals/:id', async (req, res) => {
    await httpAuth.credentials(req, { allow: ['user'] });
    const decision = req.body?.decision;
    if (decision !== 'approve' && decision !== 'reject') {
      throw new InputError('decision must be approve or reject');
    }
    const note = typeof req.body?.note === 'string' ? req.body.note.slice(0, 500) : undefined;
    await forward(res, () =>
      api.decide(req.header(PLATFORM_TOKEN_HEADER) ?? '', req.params.id, decision, note),
    );
  });

  return router;
}
