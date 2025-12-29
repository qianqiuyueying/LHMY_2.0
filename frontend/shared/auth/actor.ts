export type ActorType = 'ADMIN' | 'PROVIDER' | 'PROVIDER_STAFF' | 'DEALER'

export function isAdmin(actorType?: ActorType): boolean {
  return actorType === 'ADMIN'
}

export function isProvider(actorType?: ActorType): boolean {
  return actorType === 'PROVIDER' || actorType === 'PROVIDER_STAFF'
}

export function isDealer(actorType?: ActorType): boolean {
  return actorType === 'DEALER'
}


