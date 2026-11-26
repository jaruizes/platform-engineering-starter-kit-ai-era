# Portal branding

Everything that makes the portal look like one organization lives in this folder, so a company or a client gets its own portal without changing code:

| File | What it is |
|---|---|
| `branding.yaml` | Title of the portal, organization name, texts of the sign-in page and of the home page welcome card, and which images to use |
| `logo.svg` | Sidebar logo when the sidebar is open: wide, about 4:1, readable on a dark background |
| `logo-icon.svg` | Sidebar logo when the sidebar is closed: square |
| favicon | The browser tab icon. Here it is `logo-icon.svg`; it can be an `.ico`, `.png` or `.svg` |

Images can be SVG or PNG. Their names are the ones in `branding.yaml`; remove a line there to show the Backstage image instead.

## Branding the portal for someone else

1. Copy this folder outside the repository, for example to `~/acme-branding`.
2. Replace the images and change the texts of `branding.yaml`.
3. Start the platform with it:

   ```bash
   BRANDING_DIR=~/acme-branding make up
   ```

The portal image is built with this folder as its last layer, so changing only the branding rebuilds it in seconds. Without `BRANDING_DIR`, `make up` uses this folder.

## How it works

- The [Dockerfile](../Dockerfile) copies the folder to `branding/` in the image, its images are served under `/branding/`, and the portal starts with `--config branding/branding.yaml` merged over `app-config.yaml`.
- The keys under `app.branding` are declared in [`packages/app/config.d.ts`](../packages/app/config.d.ts), so the browser can read them.
- The tab title, the description and the favicon are set in [`index.html`](../packages/app/public/index.html) when the page is served; the logos, the sign-in page and the welcome card read the configuration in the browser.
