export type EnvelopeOk<T> = { success: true; data: T; requestId?: string; error?: null }

export type EnvelopeFail = {
  success: false
  data?: null
  requestId?: string
  error: { code: string; message: string; details?: unknown }
}

export type Envelope<T> = EnvelopeOk<T> | EnvelopeFail

export function isEnvelopeOk<T>(x: unknown): x is EnvelopeOk<T> {
  return !!x && typeof x === 'object' && (x as any).success === true && 'data' in (x as any)
}

export function isEnvelopeFail(x: unknown): x is EnvelopeFail {
  return !!x && typeof x === 'object' && (x as any).success === false && !!(x as any).error
}

export function getEnvelopeRequestId(x: unknown): string | undefined {
  if (!x || typeof x !== 'object') return undefined
  const rid = (x as any).requestId
  return typeof rid === 'string' && rid ? rid : undefined
}


