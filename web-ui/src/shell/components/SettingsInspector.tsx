import { useState } from 'react'
import { CONTACT_EMAIL } from '@/lib/contact'
import styles from './SettingsInspector.module.css'

type Props = {
  dimmed: boolean
  onToggleDim: () => void
}

type Tab = 'settings' | 'help'

export function SettingsInspector({ dimmed, onToggleDim }: Props) {
  const [tab, setTab] = useState<Tab>('settings')

  return (
    <aside className={styles.panel} aria-label="Settings inspector">
      <div className={styles.tabs} role="tablist" aria-label="Settings panels">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'settings'}
          className={tab === 'settings' ? styles.tabActive : styles.tab}
          onClick={() => setTab('settings')}
        >
          Settings
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'help'}
          className={tab === 'help' ? styles.tabActive : styles.tab}
          onClick={() => setTab('help')}
        >
          Help
        </button>
      </div>

      {tab === 'settings' ? (
        <>
          <section className={styles.section}>
            <h3>Canvas</h3>
            <div className={styles.row}>
              <span>Size</span>
              <strong>768 × 1024</strong> model · extended paper 1280 × 1536
            </div>
            <div className={styles.row}>
              <span>Background</span>
              <strong>Cream paper</strong>
            </div>
            <div className={styles.row}>
              <span>Dim reference</span>
              <button
                type="button"
                className={dimmed ? styles.toggleOn : styles.toggle}
                aria-pressed={dimmed}
                aria-label={dimmed ? 'Dim reference on' : 'Dim reference off'}
                onClick={onToggleDim}
              />
            </div>
          </section>

          <section className={styles.section}>
            <h3>Shortcuts</h3>
            <div className={styles.shortcuts}>
              <div className={styles.shortcut}>
                <span>Pencil</span>
                <span className={styles.kbd}>B</span>
              </div>
              <div className={styles.shortcut}>
                <span>Eraser</span>
                <span className={styles.kbd}>E</span>
              </div>
              <div className={styles.shortcut}>
                <span>Fill</span>
                <span className={styles.kbd}>G</span>
              </div>
              <div className={styles.shortcut}>
                <span>Eyedropper</span>
                <span className={styles.kbd}>I</span>
              </div>
              <div className={styles.shortcut}>
                <span>Brush size</span>
                <span className={styles.kbd}>Alt + wheel</span>
              </div>
              <div className={styles.shortcut}>
                <span>Undo</span>
                <span className={styles.kbd}>Ctrl + Z</span>
              </div>
              <div className={styles.shortcut}>
                <span>Redo</span>
                <span className={styles.kbd}>Ctrl + Shift + Z</span>
              </div>
            </div>
          </section>
        </>
      ) : (
        <div className={styles.help} data-testid="settings-help">
          <section className={styles.section}>
            <h3>Studio basics</h3>
            <ul className={styles.helpList}>
              <li>Draw on the model, then use Magic to polish a sketch or Try On Person for a photo preview.</li>
              <li>Switch Models to change the figure. Your designs stay on the current sketch until you save.</li>
              <li>Stars power Magic, Create Model, fabric, and PDF. Tap the star count in the header to refill.</li>
            </ul>
          </section>

          <section className={styles.section}>
            <h3>Tips</h3>
            <ul className={styles.helpList}>
              <li>Fill closed shapes for cleaner Magic and Try On results.</li>
              <li>Try On Person is a concept preview on your Create Model photo — not a fit guarantee.</li>
              <li>Save to My Designs or My Looks when you want to keep a version.</li>
            </ul>
          </section>

          <section className={styles.section}>
            <h3>Contact</h3>
            <p className={styles.helpCopy}>
              Questions or feedback? Email{' '}
              <a className={styles.helpLink} href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </a>
              , or open <strong>My Studio → Contact us</strong>.
            </p>
            <p className={styles.helpCopy}>
              <a className={styles.helpLink} href="/privacy">
                Privacy Policy
              </a>
            </p>
          </section>
        </div>
      )}
    </aside>
  )
}
