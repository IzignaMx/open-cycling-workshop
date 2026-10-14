interface ViewIdentity {
  user_id: string
  organization_id: string
  location_id: string | null
}
interface ViewTicket {
  generation: number
  userId: string | null
  organizationId: string | null
  locationId: string | null
}
/** In-memory lifetime guard, not authorization. Server capability checks stay authoritative. */
export class SessionViewGeneration {
  private generation = 0
  advance(): number {
    return ++this.generation
  }
  isGenerationCurrent(generation: number): boolean {
    return this.generation === generation
  }
  capture(user: ViewIdentity | null): ViewTicket {
    return {
      generation: this.generation,
      userId: user?.user_id ?? null,
      organizationId: user?.organization_id ?? null,
      locationId: user?.location_id ?? null,
    }
  }
  isCurrent(ticket: ViewTicket, user: ViewIdentity | null): boolean {
    return (
      ticket.generation === this.generation &&
      ticket.userId === (user?.user_id ?? null) &&
      ticket.organizationId === (user?.organization_id ?? null) &&
      ticket.locationId === (user?.location_id ?? null)
    )
  }
}
