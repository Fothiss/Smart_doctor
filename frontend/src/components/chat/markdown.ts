/**
 * Нормализация разметки ответа.
 *
 * Модель регулярно возвращает перечисление одной строкой: «принципы: - первый 1. - второй».
 * Для markdown такой дефис — обычный символ внутри абзаца, поэтому список схлопывается в
 * портянку. Здесь пункты разводятся по строкам; текст без признаков перечисления остаётся как
 * есть, а дефисы внутри слов и диапазонов («АГ 2-й степени», «5-10 мг») не трогаются.
 */

const DASH_BULLET = /(^|[\s.;:!?)»])([-–—•])\s+(?=\S)/g
const NUMBERED_BULLET = /(^|\s)(\d{1,2})\.\s+(?=\S)/g

function count(text: string, pattern: RegExp): number {
  return (text.match(pattern) ?? []).length
}

/**
 * Развести пункты перечисления по строкам.
 *
 * Одиночный дефис разводится только перед заглавной буквой или цифрой: «лечение - это…»
 * списком не является, а «- При ХБП…» — является. Если в тексте два и более маркеров,
 * считаем, что это список, и разводим все.
 */
export function normalizeLists(text: string): string {
  const source = text.replace(/\r\n/g, '\n')
  let result = source

  const dashes = count(result, DASH_BULLET)
  if (dashes >= 2) {
    result = result.replace(
      DASH_BULLET,
      (_match, lead: string, bullet: string) => `${lead}${separator(lead)}${bullet} `,
    )
  } else if (dashes === 1) {
    result = result.replace(
      /(^|[\s.;:!?)»])([-–—•])\s+(?=[A-ZА-ЯЁ0-9"])/g,
      (_match, lead: string, bullet: string) => `${lead}${separator(lead)}${bullet} `,
    )
  }

  const numbered = count(result, NUMBERED_BULLET)
  if (numbered >= 2) {
    // Нумерованный список — только когда пунктов несколько: «5. 5 мг» — это дозировка
    result = result.replace(
      NUMBERED_BULLET,
      (_match, lead: string, n: string) => `${lead}${separator(lead)}${n}. `,
    )
  }

  return result
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/^\n+/, '')
}

/** Перевод строки перед пунктом: уже стоящий перенос не удваиваем. */
function separator(lead: string): string {
  return lead.includes('\n') ? '' : '\n'
}
