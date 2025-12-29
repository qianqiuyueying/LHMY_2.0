export type CmsChannel = {
  id: string
  name: string
  sort: number
  status: 'ENABLED' | 'DISABLED'
  createdAt: string
  updatedAt: string
}

export type CmsContentListItem = {
  id: string
  channelId: string
  title: string
  coverImageUrl?: string | null
  summary?: string | null
  publishedAt?: string | null
}

export type CmsContentDetail = {
  id: string
  channelId: string
  title: string
  coverImageUrl?: string | null
  summary?: string | null
  contentHtml: string
  publishedAt?: string | null
}

