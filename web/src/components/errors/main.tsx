export const MainErrorFallback = () => {
  return (
    <div
      className="flex h-screen w-screen flex-col items-center justify-center text-red-600"
      role="alert"
    >
      <h2 className="text-lg font-semibold">Algo deu errado</h2>
      <button className="mt-4" onClick={() => window.location.assign(window.location.origin)}>
        Recarregar
      </button>
    </div>
  )
}
