# ${{ values.name }}

${{ values.description }}

Angular frontend built and deployed through the platform Golden Path. See
`AGENTS.md` and the `frontend-angular-v1` architecture rules before implementing
features. Requests to the backend use relative `/api/` URLs; the Kubernetes App
resource can route them to `${{ values.backendService }}` in the same environment.

```sh
npm install
npm start
npm test
npm run build
```
