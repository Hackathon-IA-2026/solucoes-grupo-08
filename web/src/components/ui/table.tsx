import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    // `relative`: um `sr-only` sem left/top posicionado dentro da tabela usa a posição estática
    // como âncora; sem um ancestral posicionado aqui perto, ele escapa para o primeiro que achar
    // (às vezes a página inteira) e força rolagem lateral do documento.
    <div className="relative w-full overflow-x-auto">
      <table className={cn('w-full caption-bottom text-sm', className)} {...props} />
    </div>
  )
}

function TableHeader({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={cn('border-b border-border bg-surface-secondary', className)} {...props} />
  )
}

function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={className} {...props} />
}

function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        'border-b border-border transition-colors last:border-0 hover:bg-surface-secondary/60',
        className,
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        'h-10 whitespace-nowrap px-3 text-left align-middle text-[0.8125rem] font-semibold text-text-secondary',
        className,
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('p-3 align-middle text-text-primary', className)} {...props} />
}

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell }
