'use client'
import { scrollAreaListChildren } from '@/components/ui/scroll-area'

import * as React from 'react'
import { useMorph } from '@/lib/cojeev-motion/use-morph'
import { cva } from 'class-variance-authority'
import { cn } from '@/utils/cn'
import * as Primitive from '@radix-ui/react-context-menu'
import { useFlowAppearance, useFlowGroup } from '@/lib/cojeev-motion/use-flow'

import {
  adornMenuItem,
  itemText,
  type ItemAdornmentItemProps,
} from '@/components/ui/item-adornment'
import { StateChevron, AnimatedIcon } from '@/components/ui/animated-icon'

export type ContextMenuProps = React.ComponentProps<typeof Primitive.Root>
export function ContextMenu(props: ContextMenuProps) {
  return <Primitive.Root {...props} />
}
export type ContextMenuPortalProps = React.ComponentProps<typeof Primitive.Portal>
export function ContextMenuPortal(props: ContextMenuPortalProps) {
  return <Primitive.Portal {...props} />
}
export type ContextMenuGroupProps = React.ComponentProps<typeof Primitive.Group>
export function ContextMenuGroup(props: ContextMenuGroupProps) {
  return <Primitive.Group data-slot="context-menu-group" {...props} />
}
export type ContextMenuRadioGroupProps = React.ComponentProps<typeof Primitive.RadioGroup>
export function ContextMenuRadioGroup(props: ContextMenuRadioGroupProps) {
  return <Primitive.RadioGroup data-slot="context-menu-radiogroup" {...props} />
}
export type ContextMenuSubProps = React.ComponentProps<typeof Primitive.Sub>
export function ContextMenuSub(props: ContextMenuSubProps) {
  return <Primitive.Sub {...props} />
}
export type ContextMenuTriggerProps = React.ComponentProps<typeof Primitive.Trigger>
export function ContextMenuTrigger({
  className,
  ref,
  onKeyDown,
  ...props
}: ContextMenuTriggerProps) {
  return (
    <Primitive.Trigger
      ref={ref}
      data-slot="context-menu-trigger"
      data-part="trigger"
      data-context=""
      tabIndex={0}
      onKeyDown={(event) => {
        onKeyDown?.(event)
        if (event.defaultPrevented || props.disabled) return
        if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
          event.preventDefault()
          const rect = event.currentTarget.getBoundingClientRect()
          event.currentTarget.dispatchEvent(
            new MouseEvent('contextmenu', {
              bubbles: true,
              cancelable: true,
              clientX: rect.left + rect.width / 2,
              clientY: rect.top + rect.height / 2,
            }),
          )
        }
      }}
      className={cn('', className)}
      {...props}
    />
  )
}
export const contextmenuContentVariants = cva(
  'v-menu [background:var(--popover)] [border-radius:var(--r-card-sm)] [padding:var(--s-2)] min-w-50 [box-shadow:var(--shadow-float)] [border:1px_solid_var(--v-border)] grid gap-0.5',
)
export type ContextMenuContentProps = React.ComponentProps<typeof Primitive.Content>
export function ContextMenuContent({
  className,
  ref,
  children,
  ...props
}: ContextMenuContentProps) {
  const morphRef = useMorph<HTMLDivElement>('surfaces', ref)
  const groupRef = useFlowGroup<HTMLDivElement>(morphRef, {
    itemSelector: '.v-menu__item',
    activeSelector: '[data-highlighted]',
  })
  const flowRef = useFlowAppearance<HTMLDivElement>(true, groupRef, 'grow')
  return (
    <Primitive.Portal>
      <Primitive.Content
        ref={flowRef}
        data-slot="context-menu-content"
        data-part="content"
        className={cn(contextmenuContentVariants(), className)}
        {...props}
      >
        {scrollAreaListChildren(children, props.asChild)}
      </Primitive.Content>
    </Primitive.Portal>
  )
}
export type ContextMenuSubContentProps = React.ComponentProps<typeof Primitive.SubContent>
export function ContextMenuSubContent({
  className,
  children,
  ref,
  ...props
}: ContextMenuSubContentProps) {
  const morphRef = useMorph<HTMLDivElement>('surfaces', ref)
  const groupRef = useFlowGroup<HTMLDivElement>(morphRef, {
    itemSelector: '.v-menu__item',
    activeSelector: '[data-highlighted]',
  })
  const flowRef = useFlowAppearance<HTMLDivElement>(true, groupRef, 'grow')
  return (
    <Primitive.Portal>
      <Primitive.SubContent
        ref={flowRef}
        data-slot="context-menu-sub-content"
        data-part="content"
        className={cn(contextmenuContentVariants(), className)}
        {...props}
      >
        {scrollAreaListChildren(children, props.asChild)}
      </Primitive.SubContent>
    </Primitive.Portal>
  )
}
export type ContextMenuItemProps = React.ComponentProps<typeof Primitive.Item> & {
  variant?: 'default' | 'danger'
  inset?: boolean
} & ItemAdornmentItemProps
export function ContextMenuItem({
  className,
  children,
  adornment,
  adornmentId,
  variant,
  inset,
  ref,
  ...props
}: ContextMenuItemProps) {
  const morphRef = useMorph<HTMLDivElement>('nav', ref)
  return (
    <Primitive.Item
      ref={morphRef}
      data-slot="context-menu-item"
      data-part="item"
      data-inset={inset || undefined}
      className={cn(
        'v-menu__item flex items-center gap-(--s-3) min-h-10 px-(--s-3) rounded-(--r-md) text-(length:--fs-control) w-full text-left whitespace-nowrap outline-none',
        variant === 'danger' && '-danger',
        className,
      )}
      {...props}
    >
      {adornMenuItem(
        children,
        adornment,
        adornmentId ?? props.textValue ?? props.id ?? itemText(children),
        props.asChild,
      )}
    </Primitive.Item>
  )
}
export type ContextMenuSubTriggerProps = React.ComponentProps<typeof Primitive.SubTrigger> & {
  inset?: boolean
} & ItemAdornmentItemProps
export function ContextMenuSubTrigger({
  className,
  adornment,
  adornmentId,
  inset,
  children,
  ref,
  ...props
}: ContextMenuSubTriggerProps) {
  const morphRef = useMorph<HTMLDivElement>('nav', ref)
  return (
    <Primitive.SubTrigger
      ref={morphRef}
      data-slot="context-menu-sub-trigger"
      data-part="item"
      data-inset={inset || undefined}
      className={cn('v-menu__item', className)}
      {...props}
    >
      {adornMenuItem(
        children,
        adornment,
        adornmentId ?? props.textValue ?? props.id ?? itemText(children),
        props.asChild,
        <StateChevron direction="right" />,
      )}
    </Primitive.SubTrigger>
  )
}
export type ContextMenuCheckboxItemProps = React.ComponentProps<typeof Primitive.CheckboxItem> &
  ItemAdornmentItemProps
export function ContextMenuCheckboxItem({
  className,
  adornment,
  adornmentId,
  children,
  ref,
  ...props
}: ContextMenuCheckboxItemProps) {
  const morphRef = useMorph<HTMLDivElement>('nav', ref)
  return (
    <Primitive.CheckboxItem
      ref={morphRef}
      data-slot="context-menu-checkbox-item"
      data-part="item"
      className={cn('v-menu__item', className)}
      {...props}
    >
      {adornMenuItem(
        children,
        adornment,
        adornmentId ?? props.textValue ?? props.id ?? itemText(children),
        props.asChild,
        <span className="v-menu__check" aria-hidden="true">
          <Primitive.ItemIndicator data-slot="context-menu-item-indicator" data-part="indicator">
            <AnimatedIcon name="check" preset="validation" />
          </Primitive.ItemIndicator>
        </span>,
      )}
    </Primitive.CheckboxItem>
  )
}
export type ContextMenuRadioItemProps = React.ComponentProps<typeof Primitive.RadioItem> &
  ItemAdornmentItemProps
export function ContextMenuRadioItem({
  className,
  adornment,
  adornmentId,
  children,
  ref,
  ...props
}: ContextMenuRadioItemProps) {
  const morphRef = useMorph<HTMLDivElement>('nav', ref)
  return (
    <Primitive.RadioItem
      ref={morphRef}
      data-slot="context-menu-radio-item"
      data-part="item"
      className={cn('v-menu__item', className)}
      {...props}
    >
      {adornMenuItem(
        children,
        adornment,
        adornmentId ?? props.textValue ?? props.id ?? itemText(children),
        props.asChild,
        <span className="v-menu__check" aria-hidden="true">
          <Primitive.ItemIndicator data-slot="context-menu-item-indicator" data-part="indicator">
            <AnimatedIcon name="dot" preset="validation" />
          </Primitive.ItemIndicator>
        </span>,
      )}
    </Primitive.RadioItem>
  )
}
export type ContextMenuLabelProps = React.ComponentProps<typeof Primitive.Label>
export function ContextMenuLabel({ className, ...props }: ContextMenuLabelProps) {
  return (
    <Primitive.Label
      data-slot="context-menu-label"
      data-part="group"
      className={cn('v-menu__group', className)}
      {...props}
    />
  )
}
export type ContextMenuSeparatorProps = React.ComponentProps<typeof Primitive.Separator>
export function ContextMenuSeparator({ className, ...props }: ContextMenuSeparatorProps) {
  return (
    <Primitive.Separator
      data-slot="context-menu-separator"
      data-part="separator"
      className={cn('v-menu__sep', className)}
      {...props}
    />
  )
}
export type ContextMenuShortcutProps = React.ComponentProps<'span'>
export function ContextMenuShortcut({ className, ...props }: ContextMenuShortcutProps) {
  return (
    <span
      data-slot="context-menu-shortcut"
      className={cn('ml-auto text-[0.6875rem] text-(--muted-foreground)', className)}
      {...props}
    />
  )
}
