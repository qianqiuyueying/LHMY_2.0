export type QueryValue = string | number | boolean | null | undefined
export type QueryRecord = Record<string, QueryValue | QueryValue[]>

export type SetQueryOpts = {
  /**
   * true: 跳过 ""（空字符串）；false: 保留空字符串
   * 默认：true（更符合“未填写就不传参”）
   */
  skipEmptyString?: boolean
}

export function setQueryParams(sp: URLSearchParams, query: QueryRecord, opts?: SetQueryOpts): void {
  const skipEmpty = opts?.skipEmptyString !== false

  for (const [k, v] of Object.entries(query)) {
    if (v === null || v === undefined) continue

    if (Array.isArray(v)) {
      for (const item of v) {
        if (item === null || item === undefined) continue
        const s = String(item)
        if (skipEmpty && s.trim() === '') continue
        sp.append(k, s)
      }
      continue
    }

    const s = String(v)
    if (skipEmpty && s.trim() === '') continue
    sp.set(k, s)
  }
}


