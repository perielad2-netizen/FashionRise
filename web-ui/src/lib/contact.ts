/** Public support inbox — messages from Contact Us land here. */
export const CONTACT_EMAIL = 'Fashionriseapp@gmail.com'

export type ContactMailInput = {
  subject: string
  message: string
  replyEmail?: string
  username?: string
}

export function buildContactMailto(input: ContactMailInput): string {
  const subject = input.subject.trim() || 'FashionRise message'
  const lines = [
    input.message.trim(),
    '',
    '—',
    input.username?.trim() ? `Studio user: ${input.username.trim()}` : null,
    input.replyEmail?.trim() ? `Reply to: ${input.replyEmail.trim()}` : null,
  ].filter((line): line is string => Boolean(line))

  const params = new URLSearchParams()
  params.set('subject', subject)
  params.set('body', lines.join('\n'))
  return `mailto:${CONTACT_EMAIL}?${params.toString()}`
}

/** Open the device mail app with a prefilled message to FashionRise support. */
export function openContactMail(input: ContactMailInput): void {
  const href = buildContactMailto(input)
  window.location.assign(href)
}
