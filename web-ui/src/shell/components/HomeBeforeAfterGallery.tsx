import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  getAuthorizedHomeExamples,
  type AuthorizedHomeExample,
} from '@/shell/homeAuthorizedExamples'
import styles from './HomeBeforeAfterGallery.module.css'

type Props = {
  /** Override catalog for tests. Defaults to the authorized production list. */
  examples?: readonly AuthorizedHomeExample[]
}

/**
 * Home before/after carousel (V2-0031).
 * Renders nothing when no authorized examples exist — never invents pairs.
 */
export function HomeBeforeAfterGallery({ examples }: Props) {
  const catalog = useMemo(() => getAuthorizedHomeExamples(examples), [examples])
  const catalogKey = catalog.map((row) => row.id).join('|')
  const headingId = useId()
  const trackRef = useRef<HTMLDivElement>(null)
  const suppressScrollSync = useRef(false)
  const [index, setIndex] = useState(0)
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setReducedMotion(mq.matches)
    sync()
    mq.addEventListener?.('change', sync)
    return () => mq.removeEventListener?.('change', sync)
  }, [])

  useEffect(() => {
    setIndex(0)
  }, [catalogKey])

  const scrollToIndex = useCallback(
    (next: number) => {
      const el = trackRef.current
      if (!el || catalog.length === 0) return
      const clamped = ((next % catalog.length) + catalog.length) % catalog.length
      setIndex(clamped)
      const slide = el.children[clamped] as HTMLElement | undefined
      if (!slide) return
      const left = slide.offsetLeft
      suppressScrollSync.current = true
      if (typeof el.scrollTo === 'function') {
        el.scrollTo({ left, behavior: reducedMotion ? 'auto' : 'smooth' })
      } else {
        el.scrollLeft = left
      }
      // jsdom may fire scroll with scrollLeft still 0 — keep button-selected index.
      window.setTimeout(() => {
        suppressScrollSync.current = false
      }, 0)
    },
    [catalog.length, reducedMotion],
  )

  const onTrackScroll = useCallback(() => {
    if (suppressScrollSync.current) return
    const el = trackRef.current
    if (!el || catalog.length === 0) return
    const width = el.clientWidth || 1
    const next = Math.round(el.scrollLeft / width)
    setIndex(Math.max(0, Math.min(catalog.length - 1, next)))
  }, [catalog.length])

  if (catalog.length === 0) return null

  return (
    <section
      className={styles.gallery}
      aria-labelledby={headingId}
      data-testid="home-before-after-gallery"
      data-reduced-motion={reducedMotion ? 'true' : 'false'}
    >
      <div className={styles.header}>
        <h2 id={headingId} className={styles.title}>
          Home Hero Gallery
        </h2>
        <p className={styles.subtitle}>Sketch → AI look — the FashionRise idea.</p>
      </div>

      <div className={styles.viewport}>
        <div
          ref={trackRef}
          className={styles.track}
          data-testid="home-gallery-track"
          onScroll={onTrackScroll}
          tabIndex={0}
          role="list"
          aria-label="Before and after examples"
        >
          {catalog.map((example, i) => (
            <article
              key={example.id}
              className={styles.slide}
              role="listitem"
              aria-label={`${example.title}: before and after`}
              data-testid={`home-gallery-slide-${example.id}`}
            >
              <p className={styles.slideTitle}>{example.title}</p>
              <div className={styles.pair}>
                <figure className={styles.frame}>
                  <img
                    src={example.before.src}
                    alt={example.before.alt}
                    width={example.before.width}
                    height={example.before.height}
                    className={styles.image}
                    loading={i === 0 ? 'eager' : 'lazy'}
                    decoding="async"
                    draggable={false}
                  />
                  <figcaption className={styles.caption}>Sketch</figcaption>
                </figure>
                <figure className={styles.frame}>
                  <img
                    src={example.after.src}
                    alt={example.after.alt}
                    width={example.after.width}
                    height={example.after.height}
                    className={styles.image}
                    loading={i === 0 ? 'eager' : 'lazy'}
                    decoding="async"
                    draggable={false}
                  />
                  <figcaption className={styles.caption}>AI Look</figcaption>
                </figure>
              </div>
            </article>
          ))}
        </div>
      </div>

      {catalog.length > 1 ? (
        <div className={styles.controls}>
          <button
            type="button"
            className={styles.navBtn}
            aria-label="Previous example"
            data-testid="home-gallery-prev"
            onClick={() => scrollToIndex(index - 1)}
          >
            <ChevronLeft size={20} aria-hidden />
          </button>
          <div className={styles.dots} role="tablist" aria-label="Example slides">
            {catalog.map((example, i) => (
              <button
                key={example.id}
                type="button"
                role="tab"
                aria-selected={i === index}
                aria-label={`Show example ${i + 1}: ${example.title}`}
                className={i === index ? styles.dotActive : styles.dot}
                data-testid={`home-gallery-dot-${i}`}
                onClick={() => scrollToIndex(i)}
              />
            ))}
          </div>
          <button
            type="button"
            className={styles.navBtn}
            aria-label="Next example"
            data-testid="home-gallery-next"
            onClick={() => scrollToIndex(index + 1)}
          >
            <ChevronRight size={20} aria-hidden />
          </button>
        </div>
      ) : null}
    </section>
  )
}
