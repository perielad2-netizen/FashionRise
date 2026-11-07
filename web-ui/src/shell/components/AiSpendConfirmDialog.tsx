import { useEffect, useState } from 'react'
import { ShoppingBag, Star } from 'lucide-react'
import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import styles from './AiSpendConfirmDialog.module.css'

export type AiSpendFeature = 'magic' | 'croquis' | 'pdf' | 'fabric'

const FEATURE_LABELS: Record<AiSpendFeature, string> = {
  magic: 'Magic',
  croquis: 'Create Model',
  pdf: 'Generate AI PDF',
  fabric: 'AI Fabric',
}

type Props = {
  open: boolean
  feature: AiSpendFeature
  /** Override dialog title; defaults to feature label. */
  title?: string
  cost: number
  balance: number | null
  unlimited: boolean
  busy?: boolean
  description?: string
  onCancel: () => void
  onApproved: () => void
  onOpenShop: () => void
}

/**
 * Shared approval gate for paid AI actions.
 * Approve runs the action when the wallet can cover the cost; otherwise shows
 * an insufficient-stars state with a shortcut into the Stars shop/cart.
 */
export function AiSpendConfirmDialog({
  open,
  feature,
  title,
  cost,
  balance,
  unlimited,
  busy = false,
  description,
  onCancel,
  onApproved,
  onOpenShop,
}: Props) {
  const [insufficient, setInsufficient] = useState(false)
  const label = title ?? FEATURE_LABELS[feature]
  const canAfford = unlimited || (balance ?? 0) >= cost

  useEffect(() => {
    if (!open) setInsufficient(false)
  }, [open])

  if (!open) return null

  if (insufficient) {
    return (
      <ConfirmDialog
        title="Not enough Stars"
        busy={busy}
        onEscape={onCancel}
        actions={[
          { label: 'Cancel', onClick: onCancel, variant: 'ghost' },
          {
            label: 'Get Stars',
            onClick: () => {
              onCancel()
              onOpenShop()
            },
            variant: 'primary',
          },
        ]}
      >
        <p>
          {label} needs <strong>−{cost} Stars</strong>
          {balance != null && !unlimited ? (
            <>
              . You have <strong>{balance}</strong>.
            </>
          ) : (
            '.'
          )}{' '}
          Open the Stars shop to top up your cart.
        </p>
        <p className={styles.shopHint}>
          <ShoppingBag size={14} aria-hidden /> Packages credit your wallet after checkout.
        </p>
      </ConfirmDialog>
    )
  }

  return (
    <ConfirmDialog
      title={label}
      busy={busy}
      onEscape={onCancel}
      actions={[
        { label: 'Cancel', onClick: onCancel, variant: 'ghost' },
        {
          label: canAfford ? `Approve −${cost}` : 'Approve',
          onClick: () => {
            if (canAfford) onApproved()
            else setInsufficient(true)
          },
          variant: 'primary',
        },
      ]}
    >
      {description ? <p>{description}</p> : null}
      <p className={styles.costRow}>
        <Star size={16} aria-hidden className={styles.star} />
        <span>
          This uses <strong>−{cost} Stars</strong>
          {unlimited ? (
            <> (unlimited owner wallet).</>
          ) : balance != null ? (
            <>
              . Balance: <strong>{balance}</strong>.
            </>
          ) : (
            <>.</>
          )}
        </span>
      </p>
      {!canAfford ? (
        <p className={styles.warn}>If you approve without enough Stars, we will open the shop path.</p>
      ) : null}
    </ConfirmDialog>
  )
}
