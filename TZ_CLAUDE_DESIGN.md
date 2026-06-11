# ТЗ: УЛЬТРА-СОВРЕМЕННЫЙ РЕДИЗАЙН ДАШБОРДА DARWIN COFFEE

**Статус:** Ready for Design  
**Дата:** 11.06.2026  
**Целевая аудитория:** Владелец кофейни (30–45 лет, привык к Эвотору, хочет красоты и точности)

---

## 📋 КРАТКИЙ БРИФ

Переделать текущий дашборд аналитики кофейни **Darwin Coffee** в **ультра-современный, wow-дизайн**, который:
- **Сразу даёт ответ на главный вопрос:** «Сколько я реально заработал?» (чистая прибыль, а не выручка)
- **Делает это красиво:** современная палитра, микро-анимации, премиум-ощущение
- **Работает везде:** desktop, планшет, мобильный (responsive, но приоритет — desktop/tablet)
- **Масштабируется:** готов к 100+ метрикам без перегруза интерфейса
- **Вдохновляет:** даже если прибыль низкая, интерфейс передаёт ощущение контроля и профессионализма

---

## 🎯 ТЕКУЩЕЕ СОСТОЯНИЕ (что переделываем)

### Существующий дашборд
- **Технология:** HTML5 + vanilla CSS + JavaScript (~2000 строк вёрстки)
- **Палитра:** коричнево-бежевая (кофейная), поддерживает light/dark режимы
- **Шрифты:** Bebas Neue (KPI), Syne (display), Mulish (body text)
- **Структура:**
  - **Топ:** белый бар с логотипом, переключателем дня/недели/месяца, кнопка дизайна (light/dark)
  - **Сайдбар:** чёрный (220px), навигация по разделам
  - **Контент:** таблицы P&L, KPI-карточки, простые графики, форма ввода расходов

### Секции текущего дашборда
1. **P&L Table** — таблица доходов/расходов (месячный + годовой)
2. **KPI Cards** — выручка, чистая прибыль, маржа, средний чек (большие цифры)
3. **Evotor Integration Panel** — статус подключения к Эвотору (часы, чеки, возвраты)
4. **Expense Editor** — форма редактирования расходов (зарплата, аренда, налоги и т.д.)
5. **Telegram Digest Preview** — превью отчёта, что придёт в бот
6. **Analytics Panel** — топ товаров, рейтинг бариста, прогноз месяца (сейчас демо)

### Что НЕ менять (обязательно)
- **Логика и данные:** все расчёты прибыли, формулы, источники данных остаются в Python-бэкенде
- **API/Backend:** дашборд получает JSON — ничего не должно измениться в структуре ответов
- **Функциональность:** все текущие возможности (редакт расходов, переключение периодов) остаются
- **Брендинг:** логотип «Darwin», позиционирование «реальная прибыль»

---

## 🎨 ДИЗАЙН-НАПРАВЛЕНИЕ: WOW-ФАКТОР

### Концепция: «Премиум-контроль аналитики» (инспирация от Stripe, Figma, Linear)

**Ключевые признаки современного дизайна:**
- ✨ **Микро-анимации**: мягкие переходы при наведении, subtle загрузка данных, smooth скролл
- 🎯 **Информационная иерархия**: главная метрика (чистая прибыль) доминирует, остальное вторично
- 🌈 **Свежая палитра**: минималистичная, но не скучная (ретро-коричневый ← нет, современный контраст ← да)
- 📱 **Spacing & Typography**: воздух, мягкие скругления (radius 8–12px), типографическая игра
- 🌙 **Dark mode 2.0**: не просто инверсия, а реальный dark-first дизайн
- 🎬 **Glassmorphism / Soft UI**: карточки с лёгкими фоновыми фильтрами, depth без тени
- ⚡ **Performance-friendly**: CSS, SVG, минимум JavaScript

### Палитра (предложение)
```
Primary (Успех/Прибыль):
  - #16a34a (зелёный, теплый) — основной, для главной метрики

Accent (Активное действие):
  - #ea580c (оранжевый, энергия) — кнопки, ссылки, выделение

Neutral (Фон + Text):
  - #f9f7f4 (светлый фон) или #0f0e0b (тёмный фон)
  - #1f1f1c (тёмный текст) или #faf9f7 (светлый текст)

Status:
  - #dc2626 (красный) — убытки, ошибки
  - #f59e0b (жёлтый) — внимание
  - #06b6d4 (синий) — информация

Glassmorphism фон:
  - rgba(255,255,255,0.7) + backdrop-filter: blur(10px) (свет)
  - rgba(0,0,0,0.3) + backdrop-filter: blur(10px) (темнота)
```

### Типография (предложение)
```
Display/Заголовки (KPI):
  - Font: Inter | Geo | Neue Montreal (sans-serif, больше модерна, чем Bebas)
  - Weight: 600–700
  - Size: 40–56px для главной метрики
  
Body/Основной текст:
  - Font: Inter или Geist (современные, читаемые)
  - Weight: 400–500
  - Size: 14–16px

Labels/Подписи:
  - Font: Inter (mono для чисел, sans для текста)
  - Weight: 500–600
  - Size: 12–13px
  - Case: UPPERCASE для категорий, normal для значений
```

---

## 🏗️ МАКЕТ И КОМПОНЕНТЫ

### Layout (Desktop-first, 1920x1080+)
```
┌─────────────────────────────────────────────────────────────┐
│ Logo  [Period Selector] [Search] [Alerts] [Profile] [Theme] │ ← Topbar (премиум-тонко)
├─────────────────────────────────────────────────────────────┤
│       │ Dashboard                                            │
│  Nav  ├─────────────────────────────────────────────────────│
│       │ ┌──────────────────────┐  ┌──────────────────────┐  │
│       │ │ Net Profit Card      │  │ Revenue Card         │  │
│       │ │ 899,565 ₽            │  │ 3,733,684 ₽          │  │
│       │ │ ↑ 12% vs last month   │  │ ↑ 5% vs last month   │  │
│       │ └──────────────────────┘  └──────────────────────┘  │
│       ├─────────────────────────────────────────────────────│
│       │ P&L Breakdown (интерактивная таблица)              │
│       │ • Revenue                                          │
│       │ • COGS (себестоимость)                             │
│       │ • Gross Margin                                     │
│       │ • Operating Expenses (развёртывается)              │
│       │ • Net Profit                                       │
│       ├─────────────────────────────────────────────────────│
│       │ [Analytics Grid]  [Evotor Status]  [Alerts]       │
│       └─────────────────────────────────────────────────────│
```

### Основные компоненты

#### 1. **Metric Card** (KPI-карточка)
```
┌────────────────────────────────┐
│ Net Profit (label, 12px)       │
│                                │
│ 899 565 ₽                       │ ← big bold number
│ ↑ 12% vs last period (trend)   │ ← secondary, muted
│                                │
│ [Sparkline 30d] [Details >]    │ ← micro-chart + link
└────────────────────────────────┘

Style:
- Фон: gradient или glassmorphic
- Hover: lift effect (transform: translateY(-2px)), shadow increase
- Animation: числа считаются при загрузке (counter animation)
```

#### 2. **P&L Table** (переделка)
```
Current → Новое
────────────────
Скучная таблица → Интерактивная, с:
- Цветными лентами слева (зелёный = прибыль, красный = убыток)
- Expand/collapse по категориям (Opex → Rent, Payroll, etc)
- Inline-редактирование (double-click на число)
- Sparkline (мини-график) для каждой строки (тренд за 12 мес)
- Сравнение: месяц vs год (две колонки, всегда видны)
- Мобиль: свайп для показа/скрытия колонок
```

#### 3. **Period Selector** (современный вид)
```
Было: [День] [Неделя] [Месяц] [Год] кнопки
Станет: Красивый dropdown / segmented control
- Дополнить: календарь (pick date range)
- Быстрые фильтры: Today | Last 7d | Last 30d | Last 90d | Custom
- Сохрани выбор в localStorage
```

#### 4. **Analytics Grid** (новый уровень)
```
Макет: 2-3 колонки (авто-адаптив)

┌─────────────────┐  ┌─────────────────┐
│ Top Products    │  │ Peak Hours      │
│ 1. Cappuccino   │  │ 9AM: 125 чеков  │
│    ↑ 234₽ profit│  │ 2PM: 98 чеков   │
│ 2. Espresso     │  │ ...             │
└─────────────────┘  └─────────────────┘

┌─────────────────────────────────────┐
│ Monthly Forecast (прогноз месяца)   │
│ Expected: 950k ₽ (↑8% vs avg)       │
│ [Progress bar с трендом]            │
└─────────────────────────────────────┘
```

#### 5. **Sidebar Navigation** (современный стиль)
```
Darwin Coffee
─────────────
📊 Dashboard       (active, highlight)
📈 Analytics
🔗 Evotor Status
💰 Expenses
📧 Bot Digest
⚙️  Settings

─────────────
🌙 [Theme toggle]
👤 Account
? Help
```

#### 6. **Alerts / Status Bar** (новое, для Evotor + система)
```
┌─────────────────────────────────────────────┐
│ ⚠️  Evotor: Syncing (last: 2 min ago)      │
│ ✅ All expenses up to date                  │
│ 📧 Bot: Ready (next digest at 07:00)        │
└─────────────────────────────────────────────┘

Animate:
- Smooth badge pulse для loading
- Green checkmark с фадовой анимацией
- Dismiss-button для alerts
```

---

## 🎬 АНИМАЦИИ И ИНТЕРАКТИВНОСТЬ

### Microinteractions (обязательно)
- **Hover на карточку:** transluscent overlay, shadow, slight scale (1.02x)
- **Click на число:** inline-edit mode (input поле фокусируется, highlight жёлтый)
- **Загрузка данных:** skeleton-screen (pulse animation) вместо пустоты
- **Переключение периода:** fade-in для новых данных + числа пересчитываются (counter)
- **Scroll топбара:** он становится меньше / появляется sticky-версия (compact)
- **Sidebar toggle:** smooth slide-out на мобилях

### Dark Mode Transition
- Toggle-кнопка (`☀️` / `🌙`) в топбаре
- Transition: 0.25s ease (не резко, лёгко)
- Сохран выбор в localStorage

---

## 📱 АДАПТИВНОСТЬ

### Breakpoints
| Screen | Layout | Priority | Comments |
|--------|--------|----------|----------|
| 1920px+ | Desktop (full) | Main | 3-column grid, все карточки рядом |
| 1366px | Desktop (1024+) | High | 2-column grid, сайдбар может скрываться |
| 768px | Tablet | Medium | 1-column grid, сайдбар скрывается (hamburger) |
| 480px | Mobile | Lower | Vertical stack, минимум информации (только KPI + main chart) |

### Mobile Priorities
1. **KPI Cards** (полная ширина, большой текст)
2. **Main P&L Table** (горизонтальный скролл, stick первая колонка)
3. **Analytics** (карусель / свайп)
4. **Expenses Form** (drawer внизу, modal)

---

## 📊 СТРАНИЦЫ И РАЗДЕЛЫ (финальная структура)

### 1. Dashboard (главная) ✅
- KPI Cards (выручка, прибыль, маржа, средний чек)
- P&L Table (месячная + годовая)
- Quick actions (редактировать расходы, скачать отчёт)

### 2. Analytics (новое, развёрнутое)
- Top products (по прибыльности, не по выручке)
- Sales forecast (месяца + квартала)
- Hour-by-hour (когда пик доходов)
- Barista ratings (if available)
- Comparison (неделя-к-неделе, месяц-к-месяцу)

### 3. Evotor Integration Status
- Sync health (последнее обновление, ошибки)
- Live receipts (демо-таблица, когда подключится)
- Payment methods breakdown
- Returns & refunds

### 4. Expense Management
- Таблица расходов (зарплата, аренда, налоги, маркетинг, etc)
- Inline-редактирование
- История версий (когда что было изменено)
- Reconciliation с Excel (если будет)

### 5. Bot Digest Preview
- Как выглядит отчёт в Telegram
- Скопировать текст
- Отправить тестовое сообщение

---

## 🛠️ ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ

### Frontend Stack (не менять!)
- **Language:** Vanilla JS (no frameworks) или лёгкий Alpine.js
- **CSS:** Pure CSS (no Tailwind, SASS OK)
- **Libs:** Chart.js / D3.js (для графиков), если нужно
- **Builds:** Static HTML (templated, автогенерируется из `backend/dashboard.py`)
- **Performance:** <100KB CSS, <200KB JS (gzipped)

### Integration Points
- **Backend:** Python-бэкенд возвращает JSON с:
  ```json
  {
    "dashboard": {
      "kpis": {"revenue": 3733684, "net_profit": 899565, "margin": 24.1},
      "pl_table": [{"category": "Revenue", "month": 312000, "ytd": 3733684}, ...],
      "analytics": {"top_products": [...], "forecast": {...}},
      "evotor_status": {"synced_at": "2026-06-11T18:23:00", "receipts_count": 1250, ...},
      "last_updated": "2026-06-11T18:23:00"
    }
  }
  ```
- **API Endpoints:** POST /api/dashboard/expenses (save expense edit), GET /api/dashboard (fetch all)
- **Storage:** localStorage для предпочтений (период, тема, раскрытые секции)

### Browser Support
- Chrome/Edge 90+ (desktop)
- Safari 14+ (iPad)
- Firefox 88+
- Mobile Safari 14+ (iPhone 11+)

### Accessibility
- ♿ WCAG 2.1 AA минимум
- Навигация по клавиатуре (Tab, Enter, Escape)
- Screen reader friendly (ARIA labels, semantic HTML)
- Color contrast ≥ 4.5:1 для текста

---

## 📏 ДИЗАЙН-СИСТЕМА

### Spacing
```
xs: 4px
sm: 8px
md: 16px
lg: 24px
xl: 32px
xxl: 48px
```

### Border Radius
```
sm: 4px (inputs)
md: 8px (cards, buttons)
lg: 12px (модали, контейнеры)
full: 9999px (pills, avatars)
```

### Shadows
```
Soft:    0 1px 2px rgba(0,0,0,0.05)
Light:   0 1px 3px rgba(0,0,0,0.1)
Medium:  0 4px 6px rgba(0,0,0,0.1)
Heavy:   0 10px 15px rgba(0,0,0,0.1)
```

### Transitions
```
Fast: 150ms ease-out (micro-interactions)
Normal: 250ms ease-in-out (page changes)
Slow: 400ms ease-in-out (modals, major layout shifts)
```

---

## 📋 DELIVERABLES

### Phase 1: Design System + Figma File
1. ✅ Палитра (цвета, палитра для light/dark)
2. ✅ Типография (шрифты, sizes, weights)
3. ✅ Компоненты (button, card, input, table, chart)
4. ✅ Layout grid (12-column на 1920px)
5. ✅ Figma file (shared, editable, comments ON)

### Phase 2: Desktop & Tablet Mockups
1. ✅ Dashboard (главная страница, full view)
2. ✅ Analytics detail page
3. ✅ Evotor status page
4. ✅ Expense edit modal
5. ✅ Dark mode для всех выше

### Phase 3: Mobile Mockups
1. ✅ Dashboard mobile (320px, 375px)
2. ✅ Navigation mobile (hamburger + drawer)
3. ✅ Tables mobile (horizontal scroll example)

### Phase 4: High-Fidelity Interactive Prototype
1. ✅ Figma prototype с переходами
2. ✅ Micro-animations spec (как использовать CSS)
3. ✅ Component library (all states: default, hover, active, disabled, loading)

### Phase 5: Frontend Implementation Guide
1. ✅ CSS модули (layout, typography, colors, animations)
2. ✅ HTML структура (по компонентам)
3. ✅ JavaScript hooks (для интерактивности)
4. ✅ Responsive breakpoints (exact media queries)

---

## ✨ NICE-TO-HAVE (но не обязательно)

- Иконография (SVG sprite для Dashboard icons)
- Иллюстрация-маскот (приветствие нового пользователя)
- Лайт-тема с гессень-текстурой (микро-паттерн)
- Кастомные чарты (вместо Chart.js библиотеки)
- Анимированный logo на загрузке
- Мотивирующие фразы при низкой прибыли 😄

---

## 🚀 УСПЕХ ПРОЕКТА (критерии)

✅ **Дизайн работает:**
- Владелец открывает дашборд → сразу видит чистую прибыль (главное число, видно на расстоянии)
- Не нужно скроллить на мобилях, чтобы увидеть KPI
- Вся аналитика (топ товары, прогноз) видна без перегруза

✅ **Современно и премиум:**
- Никакой скучной серости; минимализм, но не холодность
- Микро-анимации заметны (приятные, не раздражающие)
- Темная тема выглядит как отдельный дизайн, а не инверсия

✅ **Юзабильность:**
- Редактировать расходы быстро (double-click → введи → Enter)
- Переключение периода интуитивно (день/неделя/месяц выбирается за клик)
- Мобиль: свайп по таблице, всё читается на 6-дюймовом экране

✅ **Техтребования:**
- Работает в Chrome, Safari, Firefox
- Загружается <2s на медленном 3G
- Доступен для скрин-ридеров (WCAG AA)

---

## 📞 КОНТАКТЫ И УТОЧНЕНИЯ

**PM/Product Owner:** [Name, Telegram, Email]  
**Backend Developer:** Кирилл (Python, структура данных)  
**Design Review:** Раз в неделю (понедельник 10:00 UTC)

---

**Версия:** 1.0  
**Дата последнего обновления:** 11.06.2026  
**Статус:** Ready for Claude.Design
