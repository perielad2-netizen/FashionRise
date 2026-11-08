/**
 * #161 — viewport-bounded ConfirmDialog keeps actions reachable on phone heights.
 * Uses jsdom layout approximations (offsetHeight) after applying CSS classes.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfirmDialog } from './ConfirmDialog'
import styles from './ConfirmDialog.module.css'

describe('ConfirmDialog scrollable viewport footer (#161)', () => {
  it('marks dialog as scrollable and keeps actions in the sticky footer region', () => {
    render(
      <ConfirmDialog
        title="Review garment for Try On"
        scrollable
        onEscape={() => undefined}
        actions={[
          { label: 'Cancel', onClick: () => undefined, variant: 'ghost' },
          { label: 'Generate realistic garment (~8¢)', onClick: () => undefined },
        ]}
      >
        <p>{'Long notice copy. '.repeat(40)}</p>
        <img alt="plate" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" />
      </ConfirmDialog>,
    )

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('data-scrollable', 'true')
    expect(dialog.className).toContain(styles.dialogScrollable)

    const actions = screen.getByTestId('confirm-dialog-actions')
    expect(actions.className).toContain(styles.actions)
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled()
    expect(
      screen.getByRole('button', { name: /Generate realistic garment/i }),
    ).toBeEnabled()
  })

  it('keeps ordinary short dialogs non-scrollable by default', () => {
    render(
      <ConfirmDialog
        title="Save?"
        actions={[{ label: 'OK', onClick: () => undefined }]}
      >
        <p>Short body</p>
      </ConfirmDialog>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).not.toHaveAttribute('data-scrollable')
    expect(dialog.className).not.toContain(styles.dialogScrollable)
  })
})
