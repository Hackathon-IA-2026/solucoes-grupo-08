import type { HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('rounded-md bg-border motion-safe:animate-pulse', className)}
      {...props}
    />
  )
}

export { Skeleton }
