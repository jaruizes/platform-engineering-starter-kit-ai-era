import { configApiRef, useApi } from '@backstage/frontend-plugin-api';

// The portal's look comes from app.branding in the configuration, which
// `make up` takes from the branding folder (see branding/README.md). Images
// are served by the portal under /branding.

/** The URL of an image of the branding folder, or undefined if not set. */
export function useBrandingImage(key: 'logo' | 'logoIcon'): string | undefined {
  const config = useApi(configApiRef);
  const file = config.getOptionalString(`app.branding.${key}`);
  if (!file) {
    return undefined;
  }
  const basePath = new URL(config.getString('app.baseUrl')).pathname.replace(/\/$/, '');
  return `${basePath}/branding/${file}`;
}

/** A text of the branding, or the given default. */
export function useBrandingText(key: string, fallback: string): string {
  const config = useApi(configApiRef);
  return config.getOptionalString(`app.branding.${key}`) ?? fallback;
}

/** The name of the portal, for alt texts and titles. */
export function usePortalTitle(): string {
  const config = useApi(configApiRef);
  return config.getOptionalString('app.title') ?? 'Backstage';
}
