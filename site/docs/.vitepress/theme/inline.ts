import { withBase } from 'vitepress'

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

// Tiny, safe renderer for the short texts in devices/*.yaml:
// paragraphs, "- " lists, `code`, **bold**, [text](url). Everything else is escaped.
function inline(src: string): string {
  const codes: string[] = []
  let s = esc(src).replace(/`([^`]+)`/g, (_, c) => {
    codes.push(c)
    return `\u0000${codes.length - 1}\u0000`
  })
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, url) => {
    if (/^https?:\/\//.test(url))
      return `<a href="${url}" target="_blank" rel="noreferrer">${text}</a>`
    return `<a href="${withBase(url)}">${text}</a>`
  })
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`)
}

export function renderText(src?: string): string {
  if (!src) return ''
  return src
    .trim()
    .split(/\n\s*\n/)
    .map((block) => {
      const lines = block.split('\n').map((l) => l.trim())
      if (lines.every((l) => l.startsWith('- ')))
        return '<ul>' + lines.map((l) => `<li>${inline(l.slice(2))}</li>`).join('') + '</ul>'
      return `<p>${inline(lines.join(''))}</p>`
    })
    .join('')
}

export const renderInline = (s?: string) => (s ? inline(s) : '')
