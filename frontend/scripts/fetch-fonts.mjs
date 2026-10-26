/**
 * Выгрузка шрифтов Google Fonts в репозиторий.
 *
 * Приложение не обращается к внешним службам шрифтов: файлы лежат в `public/fonts`, а
 * `src/styles/fonts.css` ссылается на них локально. Скрипт нужен, чтобы обновить начертания.
 *
 * Запуск: node scripts/fetch-fonts.mjs (из каталога frontend)
 */
import { mkdir, readdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

const OUT_DIR = join('public', 'fonts')
const CSS_PATH = join('src', 'styles', 'fonts.css')
const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

/** Семейства и начертания, которые нужны интерфейсу. */
const FAMILIES = [
  { family: 'Inter', slug: 'inter', query: 'Inter:wght@400;500;600' },
  { family: 'JetBrains Mono', slug: 'jetbrains-mono', query: 'JetBrains+Mono:wght@400' },
]

/** Кириллица обязательна; latin нужен для кодов МКБ и латинских терминов. Latin-ext не нужен. */
const KEEP_SUBSETS = new Set(['latin', 'cyrillic', 'cyrillic-ext'])

const BLOCK = /\/\*\s*([\w-]+)\s*\*\/\s*(@font-face\s*\{[^}]*\})/g

async function fetchText(url) {
  const response = await fetch(url, { headers: { 'User-Agent': UA } })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`)
  }
  return response.text()
}

async function fetchBinary(url) {
  const response = await fetch(url, { headers: { 'User-Agent': UA } })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`)
  }
  return Buffer.from(await response.arrayBuffer())
}

/** Имя файла кодирует начертание: 400, 600, 400i (курсив). */
function describeWeight(block) {
  const weight = /font-weight:\s*(\d+)/.exec(block)?.[1] ?? '400'
  const italic = /font-style:\s*italic/.test(block)
  return `${weight}${italic ? 'i' : ''}`
}

await mkdir(OUT_DIR, { recursive: true })
const cssParts = []

for (const { family, slug, query } of FAMILIES) {
  const css = await fetchText(`https://fonts.googleapis.com/css2?family=${query}&display=swap`)

  for (const match of css.matchAll(BLOCK)) {
    const [, subset, block] = match
    if (!KEEP_SUBSETS.has(subset)) {
      continue
    }
    const url = /url\((https:\/\/[^)]+\.woff2)\)/.exec(block)?.[1]
    if (url === undefined) {
      continue
    }

    const fileName = `${slug}-${describeWeight(block)}-${subset}.woff2`
    await writeFile(join(OUT_DIR, fileName), await fetchBinary(url))

    cssParts.push(
      block
        .replace(/url\(https:\/\/[^)]+\.woff2\)/, `url('/fonts/${fileName}')`)
        .replace(/\s*\n\s*/g, ' ')
        .trim(),
    )
  }

  console.log(`${family}: готово`)
}

const header = `/*
 * Шрифты приложения. Файлы лежат в public/fonts и отдаются как статика: внешних запросов нет.
 * Inter — интерфейс, JetBrains Mono — коды и цифры.
 * Перегенерировать: node scripts/fetch-fonts.mjs
 */
`

await writeFile(CSS_PATH, `${header}\n${cssParts.join('\n\n')}\n`)

// Убираем файлы, которые больше не указаны в сгенерированном CSS
const used = new Set(cssParts.map((part) => /\/fonts\/([\w.-]+\.woff2)/.exec(part)?.[1]))
for (const name of await readdir(OUT_DIR)) {
  if (!used.has(name)) {
    await rm(join(OUT_DIR, name))
    console.log(`удалён ${name}`)
  }
}

console.log(`в файлах шрифтов: ${used.size}, css: ${CSS_PATH}`)
