import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { ChevronDown, LogOut, Mail, Settings, UserRound, X } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { CONTACT_EMAIL, openContactMail } from '@/lib/contact'
import styles from './GlobalHeader.module.css'

type Props = {
  leading?: ReactNode
  username: string
  onLogout: () => void
  onComingSoon?: (label: string) => void
}

type Panel = 'about' | 'contact' | null

export function GlobalHeader({ leading, username, onLogout }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [panel, setPanel] = useState<Panel>(null)
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [replyEmail, setReplyEmail] = useState('')
  const [sentHint, setSentHint] = useState<string | null>(null)
  const subjectId = useId()
  const messageId = useId()
  const replyId = useId()

  function openContact() {
    setMenuOpen(false)
    setSentHint(null)
    setPanel('contact')
  }

  function closePanel() {
    setPanel(null)
    setSentHint(null)
  }

  function onSubmitContact(event: FormEvent) {
    event.preventDefault()
    const trimmedMessage = message.trim()
    if (!trimmedMessage) return
    openContactMail({
      subject,
      message: trimmedMessage,
      replyEmail,
      username,
    })
    setSentHint(`Opening your email app to message ${CONTACT_EMAIL}.`)
  }

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        {leading}
        <img src={UI_ASSETS.brand.mark} alt="" className={styles.mark} draggable={false} />
        <p className={styles.wordmark}>
          Fashion<span>Rise</span>
        </p>
      </div>
      <p className={styles.tagline} aria-hidden>
        Dream <span className={styles.plus}>+</span> Sketch{' '}
        <span className={styles.plus}>+</span> Create
      </p>
      <div className={styles.actions}>
        <span className={styles.avatar} aria-hidden>
          <UserRound size={16} />
        </span>
        <div className={styles.menuWrap}>
          <button
            type="button"
            className={styles.studioBtn}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span>My Studio</span>
            <ChevronDown size={14} />
          </button>
          {menuOpen ? (
            <div className={styles.menu} role="menu">
              <p className={styles.menuUser}>{username}</p>
              <button
                type="button"
                role="menuitem"
                className={styles.menuItem}
                onClick={openContact}
              >
                <Mail size={14} />
                Contact us
              </button>
              <button
                type="button"
                role="menuitem"
                className={styles.menuItem}
                onClick={() => {
                  setMenuOpen(false)
                  onLogout()
                }}
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className={styles.settingsBtn}
          aria-label="Settings and About"
          title="Settings / About"
          onClick={() => {
            setSentHint(null)
            setPanel('about')
          }}
        >
          <Settings size={16} />
        </button>
      </div>

      {panel === 'about' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={styles.aboutCard}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-about-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-about-title">About FashionRise</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close about"
                onClick={closePanel}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              Dream, sketch, and create looks in your personal FashionRise studio.
            </p>
            <p className={styles.aboutBody}>
              Questions or feedback? Email{' '}
              <a className={styles.contactLink} href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </a>
              .
            </p>
            <p className={styles.aboutBody}>
              <a className={styles.contactLink} href="/privacy">
                Privacy Policy
              </a>
            </p>
            <button type="button" className={styles.contactPrimary} onClick={openContact}>
              <Mail size={14} aria-hidden />
              Contact us
            </button>
          </div>
        </div>
      ) : null}

      {panel === 'contact' ? (
        <div className={styles.aboutScrim} role="presentation" onClick={closePanel}>
          <div
            className={`${styles.aboutCard} ${styles.contactCard}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="fr-contact-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.aboutHeader}>
              <h2 id="fr-contact-title">Contact us</h2>
              <button
                type="button"
                className={styles.aboutClose}
                aria-label="Close contact"
                onClick={closePanel}
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.aboutBody}>
              Send a note to{' '}
              <a className={styles.contactLink} href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </a>
              . Your mail app opens with the message ready to send.
            </p>
            <form className={styles.contactForm} onSubmit={onSubmitContact}>
              <label className={styles.contactLabel} htmlFor={subjectId}>
                Subject
              </label>
              <input
                id={subjectId}
                className={styles.contactInput}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={120}
                placeholder="How can we help?"
                autoComplete="off"
              />
              <label className={styles.contactLabel} htmlFor={messageId}>
                Message
              </label>
              <textarea
                id={messageId}
                className={styles.contactTextarea}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={4000}
                rows={5}
                required
                placeholder="Tell us what’s going on…"
              />
              <label className={styles.contactLabel} htmlFor={replyId}>
                Your email (optional)
              </label>
              <input
                id={replyId}
                className={styles.contactInput}
                type="email"
                value={replyEmail}
                onChange={(e) => setReplyEmail(e.target.value)}
                maxLength={200}
                placeholder="so we can reply"
                autoComplete="email"
              />
              {sentHint ? (
                <p className={styles.contactHint} role="status">
                  {sentHint}
                </p>
              ) : null}
              <div className={styles.contactActions}>
                <button type="button" className={styles.contactGhost} onClick={closePanel}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.contactPrimary}
                  disabled={!message.trim()}
                >
                  <Mail size={14} aria-hidden />
                  Send message
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </header>
  )
}
