// Everything that floats over the page: modal window, sliding panel, dropdown menu, toast
import { Check, Info, TriangleAlert, X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

function useEsc(active, onClose) {
  useEffect(() => {
    if (!active) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active, onClose])
}

// While a window is open the page behind it does not scroll
function useLockScroll(active) {
  useEffect(() => {
    if (!active) return
    const before = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = before }
  }, [active])
}

function CloseButton({ onClose }) {
  const { t } = useTranslation()
  return (
    <button type="button" onClick={onClose} aria-label={t('common.close')}
      className="flex size-10 shrink-0 items-center justify-center rounded-md text-muted outline-none hover:bg-surface-2 hover:text-ink focus-visible:ring-2 focus-visible:ring-primary">
      <X className="size-5" aria-hidden />
    </button>
  )
}

// `fullOnPhone`: the whole screen on a phone (a long form), a centred window from 640 px
export function Modal({ open, onClose, title, children, footer, fullOnPhone = false }) {
  useEsc(open, onClose)
  useLockScroll(open)
  if (!open) return null
  return createPortal(
    <div className={`fixed inset-0 z-50 flex items-center justify-center ${fullOnPhone ? 'sm:p-4' : 'p-4'}`}>
      <div className="absolute inset-0 animate-[fade-in_150ms] bg-ink/50" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label={title}
        className={`relative flex max-h-full w-full animate-[pop-in_150ms] flex-col bg-surface shadow-pop ${
          fullOnPhone ? 'h-full sm:h-auto sm:max-w-lg sm:rounded-xl' : 'max-w-lg rounded-xl'}`}>
        <div className="flex items-center justify-between gap-3 px-5 pt-4">
          <h2 className="text-h2">{title}</h2>
          <CloseButton onClose={onClose} />
        </div>
        <div className="overflow-y-auto px-5 py-3">{children}</div>
        {footer && <div className="flex justify-end gap-2 px-5 pt-1 pb-5">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}

const SHEET_SIDE = {
  left: 'inset-y-0 left-0 w-[85vw] max-w-80 animate-[slide-left_200ms_ease-out]',
  right: 'inset-y-0 right-0 w-[85vw] max-w-96 animate-[slide-right_200ms_ease-out]',
  bottom: 'inset-x-0 bottom-0 max-h-[85dvh] animate-[slide-up_200ms_ease-out] rounded-t-xl',
  wide: 'inset-y-0 right-0 w-full max-w-2xl animate-[slide-right_200ms_ease-out]', // the offer editor
}

// Sliding panel: the menu on a phone (left), the catalog filters (bottom)
export function Sheet({ open, onClose, title, side = 'bottom', children, footer }) {
  useEsc(open, onClose)
  useLockScroll(open)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 animate-[fade-in_150ms] bg-ink/50" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label={title}
        className={`absolute flex flex-col bg-surface shadow-pop ${SHEET_SIDE[side]}`}>
        <div className="flex items-center justify-between gap-3 border-b border-line py-2 pr-2 pl-4">
          <div className="min-w-0 text-h3">{title}</div>
          <CloseButton onClose={onClose} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <div className="border-t border-line p-4">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}

const DropdownContext = createContext(null)

// Dropdown menu: closes on a click outside, on Esc and after choosing an item.
// `trigger` gets { open, toggle } and draws the button
// `up`: the panel opens above the trigger (a button at the bottom of a card, above the phone tab bar)
// `initialOpen`: for the static tests
export function Dropdown({ trigger, align = 'right', up = false, panelClassName = 'w-64', initialOpen = false, children }) {
  const [open, setOpen] = useState(initialOpen)
  const box = useRef(null)
  const close = useCallback(() => setOpen(false), [])
  useEsc(open, close)
  useEffect(() => {
    if (!open) return
    const onDown = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])
  return (
    <div ref={box} className="relative">
      {trigger({ open, toggle: () => setOpen(!open) })}
      {open && (
        <DropdownContext.Provider value={close}>
          <div role="menu" className={`absolute z-40 ${up ? 'bottom-full mb-2' : 'top-full mt-2'} max-w-[calc(100vw-2rem)] animate-[pop-in_120ms] rounded-lg border border-line bg-surface p-1.5 shadow-pop ${
            align === 'right' ? 'right-0' : 'left-0'} ${panelClassName}`}>
            {children}
          </div>
        </DropdownContext.Provider>
      )}
    </div>
  )
}

// One item of a dropdown: a button, or anything else through `as` (a router Link)
export function DropdownItem({ as: Tag = 'button', icon: Icon, selected, onClick, className = '', children, ...props }) {
  const close = useContext(DropdownContext)
  const extra = Tag === 'button' ? { type: 'button' } : {}
  return (
    <Tag role="menuitem" {...extra} {...props} onClick={(e) => { onClick?.(e); close?.() }}
      className={`flex min-h-10 w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm outline-none hover:bg-surface-2 focus-visible:bg-surface-2 ${selected ? 'font-semibold text-primary' : 'text-ink'} ${className}`}>
      {Icon && <Icon className="size-4 shrink-0 text-muted" aria-hidden />}
      <span className="min-w-0 flex-1">{children}</span>
      {selected && <Check className="size-4 shrink-0" aria-hidden />}
    </Tag>
  )
}

const TOAST_MS = 4000
const TOAST_STYLE = {
  success: ['border-success-line bg-success-soft text-success', Check],
  info: ['border-info-line bg-info-soft text-info', Info],
  danger: ['border-danger-line bg-danger-soft text-danger', TriangleAlert],
}
const ToastContext = createContext(() => {})

// const toast = useToast(); toast('Сохранено') or toast(text, 'danger')
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(1)
  const toast = useCallback((text, tone = 'success') => {
    const id = nextId.current++
    setToasts((prev) => [...prev, { id, text, tone }])
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), TOAST_MS)
  }, [])
  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-4 z-[60] flex flex-col items-center gap-2 md:right-6 md:left-auto md:items-end">
        {toasts.map(({ id, text, tone }) => {
          const [style, Icon] = TOAST_STYLE[tone]
          return (
            <div key={id} role="status" className={`pointer-events-auto flex max-w-sm animate-[pop-in_150ms] items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium shadow-pop ${style}`}>
              <Icon className="size-4 shrink-0" aria-hidden />{text}
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
