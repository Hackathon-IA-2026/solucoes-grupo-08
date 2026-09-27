import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Suspense, useState, type ReactNode } from 'react'
import { ErrorBoundary } from 'react-error-boundary'
import { MainErrorFallback } from '@/components/errors/main'
import { Spinner } from '@/components/ui/spinner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { queryConfig } from '@/lib/react-query'

type AppProviderProps = {
  children: ReactNode
}

export const AppProvider = ({ children }: AppProviderProps) => {
  const [queryClient] = useState(() => new QueryClient({ defaultOptions: queryConfig }))

  return (
    <Suspense
      fallback={
        <div className="flex h-screen w-screen items-center justify-center">
          <Spinner size="xl" />
        </div>
      }
    >
      <ErrorBoundary FallbackComponent={MainErrorFallback}>
        <QueryClientProvider client={queryClient}>
          <TooltipProvider delayDuration={300}>
            {import.meta.env.DEV && <ReactQueryDevtools />}
            {children}
          </TooltipProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </Suspense>
  )
}
