import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from './components/AppLayout'
import { ToastProvider } from './components/ui/Toast'
import { ChatPage } from './pages/ChatPage'
import { LibraryPage } from './pages/LibraryPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProtocolPage } from './pages/ProtocolPage'
import { ViewerPage } from './pages/ViewerPage'
import { ChatSessionProvider } from './store/chatSession'

/**
 * Маршруты приложения.
 *
 * Фильтр библиотеки и номер страницы просмотра живут в query-параметрах адреса, поэтому
 * возврат из просмотрщика восстанавливает список, а кнопка «назад» браузера работает ожидаемо.
 *
 * Отдельно от `App`, чтобы маршруты можно было отрендерить в тесте без DOM. Уведомления живут
 * внутри маршрутов: любой экран может сообщить о результате действия, не заводя свой слой.
 * Сессия чата поднята выше маршрутов: переход в библиотеку её не теряет, а перезагрузка
 * страницы начинает разговор заново.
 */
export function AppRoutes() {
  return (
    <ToastProvider>
      <ChatSessionProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/library" replace />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/:guidelineId/view" element={<ViewerPage />} />
            <Route path="/protocol/new" element={<ProtocolPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </ChatSessionProvider>
    </ToastProvider>
  )
}

/** Приложение целиком: маршруты внутри браузерного роутера. */
export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
