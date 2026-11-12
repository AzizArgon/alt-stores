# Узбекский перевод — что проверить (фаза 15)

Переводы — в `frontend/src/locales/uz.json` (латиница; буквы `oʻ`, `gʻ` — со знаком ʻ U+02BB, тутуқ белгиси — ʼ U+02BC).
Ниже — места, где я не уверен в слове. Если вариант плохой — впишите свой в последнюю колонку, я заменю по ключу.
Тексты Excel-выгрузки — отдельно, в `backend/app/core/i18n.py` (те же слова).

| Ключ | Русский | Мой вариант | Ваш вариант |
|---|---|---|---|
| `nav.builds`, `builds.title` | Готовые сборки | Tayyor yigʻmalar | |
| `cabinet.nav.builds`, `builds.*` | Сборка | Yigʻma | |
| `reservation.reserve` | Забронировать | Bron qilish | |
| `nav.reservations` | Мои брони | Mening bronlarim | |
| `upload.title`, везде «прайс» | Прайс | Prays | (или «narxlar roʻyxati»?) |
| `cabinet.nav.stock_move`, `warehouse.tabs.move` | Выкладка | Vitrinaga chiqarish | |
| `warehouse.kinds.move_out` / `move_in` | Выкладка: со склада / в филиал | Chiqarish: ombordan / filialga | |
| `cabinet.nav.stock_receipt` | Приёмка | Qabul qilish | |
| `warehouse.kinds.receipt` | Приход | Kirim | |
| `cabinet.nav.stock_stocktake` | Ревизия | Reviziya | (или «Inventarizatsiya»?) |
| `warehouse.stocktake.status.short` / `over` | Недостача / Излишек | Kamomad / Ortiqcha | |
| `warehouse.cost.markup` | Наценка | Ustama | |
| `warehouse.cost.column` | Закупка | Xarid narxi | |
| `warehouse.reasons.defect` | Брак | Brak | (или «Nuqsonli»?) |
| `warehouse.mode.stock` | Учёт остатков | Qoldiqlar hisobi | |
| `warehouse.mode.price` | Только прайс | Faqat prays | |
| `flags.dispute` | Оспорить | Eʼtiroz bildirish | |
| `flags.level.info` | К сведению | Maʼlumot uchun | |
| `import.*`, `flags.ai` | ИИ | SI (sunʼiy intellekt) | (или оставить «AI»?) |
| `price.rateHint` | курс ЦБ | MB kursi (Markaziy bank) | |
| `product.mxik` | Код МХИК | MXIK kodi | |
| `store.innStir` | ИНН (СТИР) | STIR (INN) | |
| `categories.printer`, `specs.values.type.mfp` | МФУ | KFQ (MFU) | |
| `categories.ups` | ИБП | UPS (UBP) | |
| `categories.speakers` | Колонки | Karnaylar | |
| `categories.chair` | Игровые кресла | Geymer kreslolari | |
| `categories.desktop` | Системные блоки | Tizim bloklari | |
| `specs.resolution` | Разрешение | Ruxsat | (или «Ekran oʻlchami (piksel)»?) |
| `specs.panel` | Матрица | Matritsa | |
| `specs.channels` | Схема (2.0 / 5.1) | Sxema | |
| `specs.unit.rpm` | об/мин | ayl/daq | (или «rpm»?) |
| `specs.unit.W` | Вт | Vt | (на рынке часто «W») |
| `specs.unit.MHz`, `Hz` | МГц, Гц | MHz, Hz | (оставил латинские, как в прайсах) |
| `specs.modules`, `unit.modules_*` | Комплект, планка | Toʻplam, planka | |
| `chat.reason.abuse` | Оскорбления | Haqorat | |
| `reservation.status.issued` | Выдано | Berildi | |
| `reservation.status.ready` | Готово к выдаче | Berishga tayyor | |
| `notify.markAll` | Отметить все прочитанными | Hammasi oʻqildi | |
| `scanner.focusHere` | нажмите здесь, чтобы пикать | skanerlash uchun shu yerni bosing | |
| `photo.crop`, `photo.cropper.title` | Кадрировать | Kesish | |
| `admin.subtitle` | администрирование | boshqaruv | |
| `admin.tab.users` | Люди | Odamlar | |
| `store.hoursPlaceholder` | Пн–Сб 10:00–19:00 | Du–Sh 10:00–19:00 | |

Формат чисел и дат в узбекском — как принято в Узбекистане: `1 250 000 soʻm`, `05.12.2022`, 24 часа; названия месяцев —
`yanvar … dekabr` (`frontend/src/services/lang.js`). Браузеры часто не знают узбекских форматов, поэтому так надёжнее.
