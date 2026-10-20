import { ConfirmDialog } from '@/components/studio/ConfirmDialog'
import type { OpenDesignState } from '@/hooks/useStudioEditor'

type Props = {
  state: OpenDesignState
  onConfirm: () => void
  onRetry: () => void
  onCancel: () => void
  onGoToStudio: () => void
}

function titleOf(state: OpenDesignState): string {
  if ('record' in state && state.record) return state.record.title || 'Untitled design'
  return 'this design'
}

export function OpenDesignDialog({ state, onConfirm, onRetry, onCancel, onGoToStudio }: Props) {
  const title = titleOf(state)

  switch (state.phase) {
    case 'loading':
      return (
        <ConfirmDialog
          title="Opening design"
          onEscape={onCancel}
          actions={[{ label: 'Cancel', onClick: onCancel, variant: 'ghost' }]}
        >
          <p role="status">Checking your saved design…</p>
        </ConfirmDialog>
      )
    case 'confirm':
      return (
        <ConfirmDialog
          title={`Open “${title}”?`}
          onEscape={onCancel}
          actions={[
            { label: 'Cancel', onClick: onCancel, variant: 'ghost' },
            { label: 'Replace and open', onClick: onConfirm, variant: 'primary' },
          ]}
        >
          <p>
            This replaces the sketch in your Studio working draft with a copy of this design. Undo
            history starts fresh. The saved design itself stays unchanged.
          </p>
          <p>To keep your current sketch, cancel and use Save design in Studio first.</p>
        </ConfirmDialog>
      )
    case 'unsynced':
      return (
        <ConfirmDialog
          title="Your Studio sketch is not saved yet"
          onEscape={onCancel}
          actions={[
            { label: 'Cancel', onClick: onCancel, variant: 'ghost' },
            { label: 'Retry save', onClick: onRetry, variant: 'primary' },
          ]}
        >
          <p>{state.message}</p>
          <p>
            Opening “{title}” replaces your working draft, so FashionRise waits until your current
            sketch is saved to your account. Nothing has been changed.
          </p>
        </ConfirmDialog>
      )
    case 'conflict':
      return (
        <ConfirmDialog
          title="Resolve your draft first"
          onEscape={onCancel}
          actions={[
            { label: 'Cancel', onClick: onCancel, variant: 'ghost' },
            { label: 'Go to Studio', onClick: onGoToStudio, variant: 'primary' },
          ]}
        >
          <p>
            Your working draft has a recovery conflict between this device and your account. Choose
            which draft to keep in Studio, then open “{title}” again.
          </p>
        </ConfirmDialog>
      )
    case 'opening':
      return (
        <ConfirmDialog
          title="Opening design"
          busy
          actions={[{ label: 'Cancel', onClick: onCancel, variant: 'ghost' }]}
        >
          <p role="status">Replacing your working draft with “{title}”…</p>
        </ConfirmDialog>
      )
    case 'error':
      return (
        <ConfirmDialog
          title="Could not open design"
          onEscape={onCancel}
          actions={[
            { label: 'Close', onClick: onCancel, variant: 'ghost' },
            ...(state.canRetry
              ? [{ label: 'Try again', onClick: onRetry, variant: 'primary' as const }]
              : []),
          ]}
        >
          <p role="alert">{state.message}</p>
        </ConfirmDialog>
      )
  }
}
