import { apiRequest } from '@/services/api/client'

export type StarPackage = {
  sku: string
  name: string
  stars: number
  price_usd_cents: number
  list_price_usd_cents?: number
  description: string
  available: boolean
}

export type StarCartItem = {
  package_sku: string
  name: string
  quantity: number
  stars_each: number
  stars_line: number
  price_usd_cents_each: number
  price_usd_cents_line: number
  available: boolean
}

export type StarCart = {
  id: string
  status: string
  items: StarCartItem[]
  stars_total: number
  price_usd_cents_total: number
  checkout_enabled: boolean
  checkout_note: string | null
}

export type StarsWallet = {
  ai_stars: number
  ai_stars_unlimited: boolean
  ai_stars_magic_cost: number
  ai_stars_costs: {
    magic: number
    croquis: number
    pdf: number
    fabric: number
  }
}

export async function fetchStarsWallet(): Promise<StarsWallet> {
  return apiRequest<StarsWallet>('/auth/stars')
}

export async function fetchStarPackages(): Promise<StarPackage[]> {
  const res = await apiRequest<{ packages: StarPackage[] }>('/shop/packages', { auth: false })
  return res.packages
}

export async function fetchStarCart(): Promise<StarCart> {
  return apiRequest<StarCart>('/shop/cart')
}

export async function setStarCartItem(packageSku: string, quantity: number): Promise<StarCart> {
  return apiRequest<StarCart>('/shop/cart/items', {
    method: 'PUT',
    body: { package_sku: packageSku, quantity },
  })
}

export async function clearStarCart(): Promise<StarCart> {
  return apiRequest<StarCart>('/shop/cart', { method: 'DELETE' })
}

export async function checkoutStarCart(): Promise<StarCart> {
  return apiRequest<StarCart>('/shop/cart/checkout', { method: 'POST' })
}

export function formatUsdCents(cents: number): string {
  return `$${(Math.max(0, cents) / 100).toFixed(2)}`
}
