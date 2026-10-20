import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { TITLE_MAX_LENGTH } from '@/lib/savedDesign'
import styles from './ConfirmDialog.module.css'

type Props = {
  defaultTitle: string
  saving: boolean
  error: string | null
  customReferenceOmitted: boolean
  onConfirm: (title: string) => void
  onCancel: () => void
}

export function SaveDesignDialog({
  defaultTitle,
  saving,
  error,
  customReferenceOmitted,
  onConfirm,
  onCancel,
}: Props) {
  const titleId = useId()
  const inputId = useId()
  const hintId = useId()
  const errorId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState(defaultTitle)

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    inputRef.current?.focus()
    inputRef.current?.select()
    return () => {
      if (previous && document.contains(previous)) previous.focus()
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) {
        event.stopPropagation()
        onCancel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, saving])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (saving) return
    onConfirm(title)
  }

  return (
    <div className={styles.scrim} role="presentation">
      <form
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={saving || undefined}
        onSubmit={submit}
        noValidate
      >
        <h2 id={titleId} className={styles.title}>
          Save as design
        </h2>
        <div className={styles.body}>
          <div className={styles.field}>
            <label className={styles.label} htmlFor={inputId}>
              Title
            </label>
            <input
              ref={inputRef}
              id={inputId}
              className={styles.input}
              value={title}
              maxLength={TITLE_MAX_LENGTH}
              autoComplete="off"
              spellCheck
              disabled={saving}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${errorId} ${hintId}` : hintId}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          {error ? (
            <p id={errorId} className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          <p id={hintId} className={styles.hint}>
            Saves a private copy of this sketch to My Designs. Only you can see it. Your Studio
            working draft stays as it is.
            {customReferenceOmitted
              ? ' Your custom reference image is session-only and is not saved with the design.'
              : ''}
          </p>
        </div>
        <div className={styles.actions}>
          <button type="button" className={styles.ghost} onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className={styles.primary} disabled={saving}>
            {saving ? 'Saving…' : error ? 'Try again' : 'Save design'}
          </button>
        </div>
      </form>
    </div>
  )
}
