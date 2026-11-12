export type OrderAssociations =
  | { orderId: string; status: 'loading' | 'failed' }
  | {
      orderId: string
      status: 'ready'
      customer:
        { status: 'restricted' | 'unavailable' } | { status: 'available'; id: string; name: string }
      bicycle:
        | { status: 'restricted' | 'unavailable' | 'none' }
        | { status: 'available'; id: string; brand: string; model: string | null }
    }
