import * as Primitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ComponentProps } from 'react'
import { cn } from '@/utils/cn'

/** Painel deslizante da esquerda, para navegação em tela estreita. Foco preso, ESC e clique fora fecham. */
export const Sheet = Primitive.Root
export const SheetTrigger = Primitive.Trigger
export const SheetClose = Primitive.Close
export const SheetTitle = Primitive.Title

export function SheetContent({
  className,
  children,
  ...props
}: ComponentProps<typeof Primitive.Content>) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-black/40 transition-opacity data-[state=closed]:opacity-0 data-[state=open]:opacity-100" />
      <Primitive.Content
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex h-full w-72 flex-col border-r border-border bg-surface shadow-lg outline-none',
          'transition-transform duration-200 data-[state=closed]:-translate-x-full data-[state=open]:translate-x-0',
          className,
        )}
        {...props}
      >
        <Primitive.Description className="sr-only">Menu de navegação do ARCO</Primitive.Description>
        {children}
        <Primitive.Close
          className="absolute right-3 top-3 rounded-sm text-text-muted transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          aria-label="Fechar menu"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </Primitive.Close>
      </Primitive.Content>
    </Primitive.Portal>
  )
}
