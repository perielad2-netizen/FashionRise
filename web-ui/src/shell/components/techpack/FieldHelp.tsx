import { useEffect, useId, useRef, useState } from 'react'
import type { FieldHelpDiagram } from './fieldHelpContent'
import styles from './FieldHelp.module.css'

type Props = {
  title: string
  explanation: string
  examples?: string[]
  diagram?: FieldHelpDiagram
}

function Diagram({ kind }: { kind: Exclude<FieldHelpDiagram, null | undefined> }) {
  const captions: Record<Exclude<FieldHelpDiagram, null | undefined>, string> = {
    silhouette: 'Overall garment shape vs body',
    inseam: 'Crotch → hem (inside leg)',
    rise: 'Waistband → crotch',
    shoulder: 'Shoulder point → shoulder point',
    sleeve: 'Shoulder / crown → cuff',
    length: 'HPS / waist → hem',
  }

  return (
    <div className={styles.diagram} aria-hidden>
      <svg viewBox="0 0 120 72" fill="none" stroke="currentColor" strokeWidth="1.5">
        {kind === 'silhouette' ? (
          <>
            <ellipse cx="60" cy="14" rx="8" ry="9" />
            <path d="M46 24c4 6 8 8 14 8s10-2 14-8" />
            <path d="M48 32c-6 8-8 22-6 34h36c2-12 0-26-6-34" />
          </>
        ) : null}
        {kind === 'inseam' ? (
          <>
            <path d="M48 12h24v12H48z" />
            <path d="M50 24l-6 40M70 24l6 40" />
            <path d="M52 30v30" strokeDasharray="3 2" />
            <circle cx="52" cy="30" r="1.5" fill="currentColor" />
            <circle cx="52" cy="60" r="1.5" fill="currentColor" />
          </>
        ) : null}
        {kind === 'rise' ? (
          <>
            <path d="M40 18h40v8H40z" />
            <path d="M48 26c0 10 4 18 12 22" />
            <path d="M72 26c0 10-4 18-12 22" />
            <path d="M60 26v22" strokeDasharray="3 2" />
          </>
        ) : null}
        {kind === 'shoulder' ? (
          <>
            <ellipse cx="60" cy="16" rx="7" ry="8" />
            <path d="M36 28h48" />
            <path d="M36 28c8 4 16 6 24 6s16-2 24-6" />
            <circle cx="36" cy="28" r="1.5" fill="currentColor" />
            <circle cx="84" cy="28" r="1.5" fill="currentColor" />
          </>
        ) : null}
        {kind === 'sleeve' ? (
          <>
            <path d="M40 18h20v36H40z" />
            <path d="M60 22c14 2 28 8 36 22" />
            <path d="M60 30c10 2 20 8 28 18" />
            <path d="M68 24l22 20" strokeDasharray="3 2" />
          </>
        ) : null}
        {kind === 'length' ? (
          <>
            <ellipse cx="60" cy="12" rx="6" ry="7" />
            <path d="M48 20h24l6 44H42z" />
            <path d="M60 20v44" strokeDasharray="3 2" />
            <circle cx="60" cy="20" r="1.5" fill="currentColor" />
            <circle cx="60" cy="64" r="1.5" fill="currentColor" />
          </>
        ) : null}
      </svg>
      <p className={styles.diagramCaption}>{captions[kind]}</p>
    </div>
  )
}

export function FieldHelp({ title, explanation, examples, diagram = null }: Props) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <span className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.trigger}
        aria-label={`Help: ${title}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close help"
            onClick={() => setOpen(false)}
          />
          <div
            id={panelId}
            role="dialog"
            aria-label={title}
            className={styles.popover}
          >
            <h3 className={styles.popoverTitle}>{title}</h3>
            <p className={styles.popoverBody}>{explanation}</p>
            {examples && examples.length > 0 ? (
              <ul className={styles.examples}>
                {examples.map((ex) => (
                  <li key={ex}>{ex}</li>
                ))}
              </ul>
            ) : null}
            {diagram ? <Diagram kind={diagram} /> : null}
          </div>
        </>
      ) : null}
    </span>
  )
}
