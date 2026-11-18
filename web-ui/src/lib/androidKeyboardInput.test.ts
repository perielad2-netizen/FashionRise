import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  isEditableElement,
  onAndroidEditableFocus,
  scrollEditableIntoView,
  shouldIgnoreOverlayDismiss,
} from '@/lib/androidKeyboardInput'

describe('androidKeyboardInput', () => {
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('detects input / textarea / contentEditable', () => {
    const input = document.createElement('input')
    const area = document.createElement('textarea')
    const div = document.createElement('div')
    div.setAttribute('contenteditable', 'true')
    Object.defineProperty(div, 'isContentEditable', { value: true })
    expect(isEditableElement(input)).toBe(true)
    expect(isEditableElement(area)).toBe(true)
    expect(isEditableElement(div)).toBe(true)
    expect(isEditableElement(document.createElement('button'))).toBe(false)
  })

  it('scrolls nearest and re-focuses without scroll', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    const scroll = vi.fn()
    const focus = vi.fn()
    input.scrollIntoView = scroll
    input.focus = focus as unknown as typeof input.focus

    scrollEditableIntoView(input)
    expect(scroll).toHaveBeenCalledWith({ block: 'nearest', inline: 'nearest', behavior: 'auto' })
    expect(focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it('defers focus scroll for Android keyboard settle', () => {
    vi.useFakeTimers()
    const input = document.createElement('input')
    document.body.appendChild(input)
    const scroll = vi.fn()
    input.scrollIntoView = scroll
    onAndroidEditableFocus(input)
    expect(scroll).not.toHaveBeenCalled()
    vi.advanceTimersByTime(50)
    expect(scroll).toHaveBeenCalled()
  })

  it('ignores overlay dismiss while keyboard flag is set or editable focused', () => {
    expect(shouldIgnoreOverlayDismiss()).toBe(false)
    document.documentElement.setAttribute('data-fr-keyboard', '1')
    expect(shouldIgnoreOverlayDismiss()).toBe(true)
    document.documentElement.removeAttribute('data-fr-keyboard')

    const area = document.createElement('textarea')
    document.body.appendChild(area)
    area.focus()
    expect(shouldIgnoreOverlayDismiss()).toBe(true)
  })
})
