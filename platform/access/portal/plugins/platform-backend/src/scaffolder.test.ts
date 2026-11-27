import { personToken, TOKEN_SECRET } from './scaffolder';

const signedIn = (type: string) => ({
  getInitiatorCredentials: async () => ({ principal: { type, userEntityRef: 'user:default/marta' } }),
});

describe('personToken', () => {
  it('calls the platform API with the token of the signed-in person', async () => {
    expect(await personToken({ ...signedIn('user'), secrets: { [TOKEN_SECRET]: 'martas-token' } })).toBe(
      'martas-token',
    );
  });

  it('asks the person to sign in when the form sent no token', async () => {
    await expect(personToken({ ...signedIn('user'), secrets: {} })).rejects.toThrow(/sign in/);
  });

  it('never runs a template for something that is not a person', async () => {
    await expect(
      personToken({ ...signedIn('service'), secrets: { [TOKEN_SECRET]: 'x' } }),
    ).rejects.toThrow(/AI agents use the platform MCP server/);
  });
});
