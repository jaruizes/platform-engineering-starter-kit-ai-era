export type QualityResult = {
  status: string;
  sourceCommit?: string;
  architecture?: string;
  profile?: { name: string; version: number };
  checks: Array<Record<string, unknown>>;
};

export async function readQualityResult(
  baseUrl: string,
  service: string,
): Promise<QualityResult | undefined> {
  const response = await fetch(
    `${baseUrl.replace(/\/$/, '')}/platform/${encodeURIComponent(service)}/raw/branch/platform-quality-evidence/.platform/quality/results.json`,
  );
  if (response.status === 404) return undefined;
  if (!response.ok) throw new Error(`Git server answered ${response.status}`);
  return (await response.json()) as QualityResult;
}
