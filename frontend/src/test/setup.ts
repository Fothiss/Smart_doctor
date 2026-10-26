/**
 * Подготовка DOM-тестов.
 *
 * В node-окружении этот файл ничего не делает: `window` отсутствует, а заглушки нужны только
 * Radix-компонентам и экранам, которые в браузере рассчитывают на API, отсутствующие в jsdom.
 */
if (typeof globalThis.window !== 'undefined') {
  if (globalThis.ResizeObserver === undefined) {
    globalThis.ResizeObserver = class {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    }
  }

  // jsdom не умеет прокручивать: экраны вызывают его, чтобы показать поле с ошибкой
  if (globalThis.Element.prototype.scrollIntoView === undefined) {
    globalThis.Element.prototype.scrollIntoView = function scrollIntoView(): void {}
  }
}
