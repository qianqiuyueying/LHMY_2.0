export type VenueListItem = {
  id: string
  name: string
  coverImageUrl?: string | null
  cityCode?: string | null
  provinceCode?: string | null
  countryCode?: string | null
  address?: string | null
  businessHours?: string | null
  tags?: string[] | null
}

export type VenueService = {
  id: string
  title: string
  fulfillmentType: 'SERVICE'
  productId?: string | null
}

export type VenueDetail = {
  id: string
  name: string
  logoUrl?: string | null
  coverImageUrl?: string | null
  imageUrls?: string[] | null
  description?: string | null
  address?: string | null
  lat?: number | null
  lng?: number | null
  businessHours?: string | null
  tags?: string[] | null
  contactPhone?: string | null
  contactPhoneMasked?: string | null
  services?: VenueService[]
}

