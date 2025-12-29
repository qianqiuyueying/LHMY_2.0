export type IdempotencyKeyFallback = 'weak' | 'uuidv4'

/**
 * 生成幂等键（浏览器侧）
 *
 * - 首选：`crypto.randomUUID()`（若可用）
 * - fallback='weak'：时间戳 + Math.random（与 admin 端旧实现保持一致）
 * - fallback='uuidv4'：getRandomValues 生成 RFC4122 v4（与 h5 端旧实现保持一致）
 */
export function newIdempotencyKey(opts?: { fallback?: IdempotencyKeyFallback }): string {
  if (typeof crypto !== 'undefined' && typeof (crypto as any).randomUUID === 'function') {
    return (crypto as any).randomUUID()
  }

  const fb = opts?.fallback ?? 'weak'
  if (fb === 'weak') {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
  }

  // uuidv4：保持“无 crypto.getRandomValues 时抛错”的行为（与旧实现一致）
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  // RFC4122 v4
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80

  const hex = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')

  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}


