import axios, { type AxiosError } from 'axios'

// Em dev, sem VITE_API_URL, o Vite faz proxy de /api para a API local (vite.config.ts).
// Para testar contra outra API (ex.: túnel do Cloudflare), defina VITE_API_URL no .env
// da raiz do repositório (.env.exemplo documenta; vite.config.ts aponta envDir para lá).
export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
})

type Detail = string | { msg?: string }[]

/** Erro de uma chamada à API: a mensagem legível, e o status e o `detail` para quem precisa deles. */
export class ApiError extends Error {
  readonly status: number | undefined
  readonly detail: unknown
  constructor(message: string, status: number | undefined, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/**
 * `detail` é texto nos erros da API, uma lista de `{ msg }` nos 422 de validação e um objeto com
 * `mensagem` nos conflitos.
 */
function messageFromDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'mensagem' in detail) {
    const { mensagem } = detail as { mensagem: unknown }
    if (typeof mensagem === 'string') return mensagem
  }
  if (!Array.isArray(detail)) return undefined
  const messages = (detail as Exclude<Detail, string>)
    .map((item) => item.msg)
    .filter((msg): msg is string => Boolean(msg))
  return messages.length > 0 ? messages.join(' ') : undefined
}

httpClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ detail?: unknown }>) => {
    const detail = error.response?.data?.detail
    const message = messageFromDetail(detail) ?? error.message
    return Promise.reject(new ApiError(message, error.response?.status, detail))
  },
)
