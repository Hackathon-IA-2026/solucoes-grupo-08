/**
 * Conversões dos campos numéricos digitados. Toda a normalização mora aqui: os componentes só
 * chamam estas funções, e o que sai do formulário é sempre `number | null`.
 *
 * Convenção brasileira: vírgula é o separador decimal e ponto é milhar. Na digitação, um ponto
 * sozinho também vale como decimal ("0.85"), porque é como muita gente digita fração.
 */

const MAX_INTEGER_DIGITS = 12
const MAX_MONEY_DIGITS = 12

/** "1.250" e "12.345.678": ponto agrupando milhares. "0.850" não é milhar, o zero à frente diz. */
const THOUSANDS = /^[1-9]\d{0,2}(\.\d{3})+$/

/**
 * Deixa só o que cabe num número decimal em português: dígitos e no máximo uma vírgula.
 * Tira "R$", espaço, sinal, "e" e o que mais vier. "1.250,50" vira "1250,50"; "0.85", "0,85".
 */
export function sanitizeDecimal(text: string): string {
  const cleaned = text.replace(/[^\d.,]/g, '')

  if (cleaned.includes(',')) {
    // Com vírgula, ela é o decimal e os pontos são milhar. Vírgula a mais é descartada.
    const [integer, ...rest] = cleaned.replaceAll('.', '').split(',')
    return `${integer},${rest.join('')}`
  }
  if (THOUSANDS.test(cleaned)) return cleaned.replaceAll('.', '')

  const parts = cleaned.split('.')
  return parts.length === 2 ? `${parts[0]},${parts[1]}` : parts.join('')
}

/** Texto em português para número. Vazio, ou só a vírgula, é `null`: vazio nunca vira zero. */
export function parseDecimal(text: string): number | null {
  const sanitized = sanitizeDecimal(text)
  if (sanitized === '' || sanitized === ',') return null
  return Number(sanitized.replace(',', '.'))
}

/** Inteiro digitado: só dígitos. Colar "10,5" fica 10; colar "1.000" fica 1000. */
export function parseInteger(text: string): number | null {
  const digits = sanitizeDecimal(text).split(',')[0].slice(0, MAX_INTEGER_DIGITS)
  return digits === '' ? null : Number(digits)
}

/** Decimal como o usuário lê: 0.85 vira "0,85". Sem milhar, para o texto continuar editável. */
export function formatDecimal(value: number | null): string {
  return value === null ? '' : String(value).replace('.', ',')
}

/** Dinheiro sem símbolo, sempre com duas casas: 1250.5 vira "1.250,50". O "R$" é a unidade do campo. */
export function formatMoney(value: number | null): string {
  if (value === null) return ''
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** Dinheiro com símbolo, para mensagem de erro: "R$ 1.250,50". */
export function formatCurrency(value: number): string {
  return `R$ ${formatMoney(value)}`
}

/**
 * Digitação de dinheiro: cada dígito entra pelo lado direito, em centavos. "1" é 0,01; "1250" é
 * 12,50; "125050" é 1.250,50. Apagar o último centavo de "0,01" esvazia o campo em vez de deixar
 * "0,00" preso.
 */
export function moneyFromTyping(text: string, previousText: string): number | null {
  const digits = text.replace(/\D/g, '').slice(0, MAX_MONEY_DIGITS)
  if (digits === '') return null

  const cents = Number(digits)
  if (cents === 0 && text.length < previousText.length) return null
  return cents / 100
}

/** Dinheiro colado: "R$ 1.250,50", "1.250,50" e "1250.5" valem o mesmo. Arredonda em centavos. */
export function moneyFromPaste(text: string): number | null {
  const value = parseDecimal(text)
  return value === null ? null : Math.round(value * 100) / 100
}
