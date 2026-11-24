import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  findKeyboardSafeAction,
  installGlobalEditableFocusGuards,
  installKeyboardSafeActionGuards,
  isEditableElement,
  isTextEditableElement,
  markKeyboardOverlayHost,
  onAndroidEditableFocus,
  preventKeyboardStealOnPointerDown,
  scrollEditableIntoView,
  shouldIgnoreOverlayDismiss,
} from '@/lib/androidKeyboardInput'

describe('androidKeyboardInput', () => {
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
    document.documentElement.removeAttribute('data-fr-keyboard')
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

  it('treats range/file as non-text editables', () => {
    const range = document.createElement('input')
    range.type = 'range'
    const file = document.createElement('input')
    file.type = 'file'
    const text = document.createElement('input')
    text.type = 'text'
    expect(isTextEditableElement(range)).toBe(false)
    expect(isTextEditableElement(file)).toBe(false)
    expect(isTextEditableElement(text)).toBe(true)
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

  it('marks nearest fixed fullscreen host as fr-keyboard-overlay', () => {
    const host = document.createElement('div')
    host.style.position = 'fixed'
    host.style.inset = '0'
    Object.defineProperty(host, 'getBoundingClientRect', {
      value: () => ({ top: 0, bottom: 800, height: 800, width: 400, left: 0, right: 400 }),
    })
    const input = document.createElement('input')
    host.appendChild(input)
    document.body.appendChild(host)
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
    markKeyboardOverlayHost(input)
    expect(host.classList.contains('fr-keyboard-overlay')).toBe(true)
    expect(host.dataset.frKeyboardHost).toBe('1')
  })

  it('global focusin guard applies preventScroll to every text input', () => {
    vi.useFakeTimers()
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
    const dispose = installGlobalEditableFocusGuards()
    const host = document.createElement('div')
    host.style.position = 'fixed'
    Object.defineProperty(host, 'getBoundingClientRect', {
      value: () => ({ top: 0, bottom: 800, height: 800, width: 400, left: 0, right: 400 }),
    })
    const input = document.createElement('input')
    const focusSpy = vi.spyOn(input, 'focus')
    input.scrollIntoView = vi.fn()
    host.appendChild(input)
    document.body.appendChild(host)

    input.focus()
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true })
    expect(host.classList.contains('fr-keyboard-overlay')).toBe(true)
    vi.advanceTimersByTime(50)
    expect(input.scrollIntoView).toHaveBeenCalled()
    dispose()
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

  it('finds submit and data-fr-kbd-safe actions but skips disabled', () => {
    const form = document.createElement('form')
    const submit = document.createElement('button')
    submit.type = 'submit'
    submit.textContent = 'Post'
    const send = document.createElement('button')
    send.type = 'button'
    send.setAttribute('data-fr-kbd-safe', '1')
    send.textContent = 'Send'
    const disabled = document.createElement('button')
    disabled.type = 'submit'
    disabled.disabled = true
    const cancel = document.createElement('button')
    cancel.type = 'button'
    cancel.textContent = 'Cancel'
    form.append(submit, send, disabled, cancel)
    document.body.appendChild(form)

    expect(findKeyboardSafeAction(submit)).toBe(submit)
    expect(findKeyboardSafeAction(send)).toBe(send)
    expect(findKeyboardSafeAction(disabled)).toBeNull()
    expect(findKeyboardSafeAction(cancel)).toBeNull()
  })

  it('prevents keyboard steal on first pointerdown while a text field is focused', () => {
    const form = document.createElement('form')
    const input = document.createElement('input')
    input.type = 'text'
    const post = document.createElement('button')
    post.type = 'submit'
    post.textContent = 'Post'
    form.append(input, post)
    document.body.appendChild(form)
    input.focus()
    expect(document.activeElement).toBe(input)

    const event = new MouseEvent('pointerdown', { bubbles: true, cancelable: true, button: 0 })
    Object.defineProperty(event, 'target', { value: post })
    const prevented = preventKeyboardStealOnPointerDown(event)
    expect(prevented).toBe(true)
    expect(event.defaultPrevented).toBe(true)
  })

  it('does not intercept when no text field is focused', () => {
    const post = document.createElement('button')
    post.type = 'submit'
    document.body.appendChild(post)
    const event = new MouseEvent('pointerdown', { bubbles: true, cancelable: true, button: 0 })
    Object.defineProperty(event, 'target', { value: post })
    expect(preventKeyboardStealOnPointerDown(event)).toBe(false)
    expect(event.defaultPrevented).toBe(false)
  })

  it('installKeyboardSafeActionGuards keeps focus on the field for submit pointerdown', () => {
    const dispose = installKeyboardSafeActionGuards()
    const form = document.createElement('form')
    const input = document.createElement('input')
    const post = document.createElement('button')
    post.type = 'submit'
    form.append(input, post)
    document.body.appendChild(form)
    input.focus()

    const event = new PointerEvent('pointerdown', {
      bubbles: true,
      cancelable: true,
      button: 0,
      pointerId: 1,
      pointerType: 'touch',
    })
    post.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(input)
    dispose()
  })
})
