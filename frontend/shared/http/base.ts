export function normalizeBaseUrl(raw: string | undefined | null, fallback: string): string {
  const v = String(raw ?? '').trim()
  const use = v || fallback
  return use.endsWith('/') ? use.slice(0, -1) : use
}


