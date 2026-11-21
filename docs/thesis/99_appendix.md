# ПРИЛОЖЕНИЕ А. Ключевые фрагменты программного кода

Фрагменты приведены из исходного кода системы (каталог `backend/app/services`) с небольшими сокращениями; комментарии в коде — на английском языке, как принято в проекте.

**А.1. Порядок разбора строк: кэш → правила → языковая модель** (`importer.py`, функция `parse_clean_rows`).

```
async def parse_clean_rows(db, rows, stats, on_progress=None, fresh=False, should_stop=None):
    """Cache first, then rules, and only the rest goes to the AI in big chunks."""
    keys = list({cache_key(r.ai_text) for r in rows})
    cached = {} if fresh else {c.key: c.data for c in db.scalars(
        select(ParseCache).where(ParseCache.key.in_(keys)))}
    result, pending, skipped = {}, [], 0
    for r in rows:
        hit = cached.get(cache_key(r.ai_text))
        rule = None if hit or fresh else parse_by_rules(r.name)
        if hit and hit.get("skip"):
            skipped += 1                      # the AI said earlier: not a product
        elif hit:
            result[r.row] = _preview_row(r, hit, "cache")
        elif rule:
            result[r.row] = _preview_row(r, rule, "rule")
        else:
            pending.append(r)                 # only these rows go to the AI
    size = settings.parser_chunk_rows         # 400 rows for Gemini
    chunks = [pending[i:i + size] for i in range(0, len(pending), size)]
    sem = asyncio.Semaphore(settings.parser_concurrency)

    async def worker(chunk):
        async with sem:
            try:
                items = {it["row"]: it for it in await parse_rows(chunk, stats)}
            except RuntimeError:              # quota or network: rows stay, price is known
                for r in chunk:
                    result[r.row] = _preview_row(r, None, "failed")
            else:
                for r in chunk:
                    if r.row in items:
                        result[r.row] = _preview_row(r, items[r.row], "ai")
                save_cache(db, {cache_key(r.ai_text): _cache_data(items[r.row])
                                if r.row in items else {"skip": True}
                                for r in chunk
                                if r.row not in items or cacheable(result[r.row])}, "ai")

    await asyncio.gather(*(worker(c) for c in chunks))
    return [result[k] for k in sorted(result)]
```

**А.2. Проверка значения характеристики по тексту продавца** (`ai_parser.py`, функция `spec_in_text`).

```
def spec_in_text(value: str, text: str) -> bool:
    """Is the spec value written in the row itself? Every number and word must be found.
    "4GB DDR4" matches "DDR4 4GB", "wireless" matches "беспроводные";
    "80 PLUS Bronze" does not match "Блок питания 600W", "6" does not match "1660"."""
    norm = _normalize(text)
    compact = re.sub(r"[^a-zа-я0-9.+/]", "", norm)
    tokens = [t.strip(".") for t in re.findall(r"[a-zа-я0-9.+/]+", _normalize(value))]
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    for tok in tokens:
        num = re.fullmatch(r"(\d+(?:\.\d+)?)([a-zа-я]*)", tok)
        if num and (not num[2] or num[2] in _UNITS):
            # a standalone number: not a part of "DDR4" or "1660"
            if not re.search(rf"(?<![\d.a-zа-я]){re.escape(num[1])}(?!\d)", norm):
                return False
        elif tok in _UNITS or len(tok) < 2 or tok in compact or _stem_in(tok, norm):
            continue
        elif not any(tok.startswith(en) and ru in norm for en, ru in _SYNONYMS):
            return False
    return True
```

**А.3. Ключ сведения в эталонную карточку** (`catalog.py`, функция `make_match_key`, сокращено).

```
def make_match_key(category, name, brand=None, specs=None) -> str:
    """Same product from different stores -> same key: brand + model words, any order."""
    text = f"{brand or ''} {strip_modifiers(category, name)[0]}".lower().replace("ё", "е")
    text = _MIXED_CODE.sub(lambda m: m[0].translate(_LOOKALIKES), text)  # Cyrillic look-alikes
    text = _GPU_CHIP.sub(lambda m: " ".join(filter(None, m.groups())), text)  # RTX5060Ti
    for ru, en in _RU_UNITS:
        text = re.sub(rf"(\d)\s*{ru}\b", rf"\1{en}", text)          # "16 ГБ" == "16GB"
    text = _DESCRIPTORS.sub(" ", text)                                # clocks, IPS, GDDR7...
    text = re.sub(rf"(\d)\s+({UNITS})\b", r"\1\2", text)              # "16 GB" == "16GB"
    tokens = re.findall(r"[a-zа-я0-9]+", text)
    if category == "cpu":                       # "Core i5-12400F" == "i5 12400F", OEM == BOX
        tokens = [t for t in tokens if t not in _PACK_WORDS and t != "core"]
    words = {t for t in tokens if t not in TYPE_WORDS} or set(tokens)
    for key in IDENTITY_SPECS.get(category, ()):  # e.g. DDR5 of a board, refresh rate
        value = (specs or {}).get(key)
        if isinstance(value, str):
            words |= set(re.findall(r"[a-zа-я0-9]+", value.lower()))
    return f"{category}:{' '.join(sorted(words))}"
```

**А.4. Anti-Fraud: правила кодом и подсказка модели вторым слоем** (`antifraud.py`).

```
def _price_below_market(price_usd, market_usd):
    if not price_usd or not market_usd or len(market_usd) < MARKET_MIN_OFFERS:  # 2
        return []
    mid = median(market_usd)
    ratio = price_usd / mid
    if ratio >= MARKET_WARNING:                                                 # 0.60
        return []
    level = "danger" if ratio < MARKET_DANGER else "warning"                   # 0.40
    return [_flag("price_below_market", level, "below_market",
                  percent=round((1 - ratio) * 100), median=round(mid), count=len(market_usd))]


def check_offer(row, market_usd=None, usd_rate=None):
    """Rules first; AI hints (row["ai_risks"]) only add types the rules did not find."""
    text = _text(row)                     # seller's row, article and confirmed specs only
    category = row.get("category") or "other"
    condition = row.get("condition") or "new"
    price_usd = _usd(row, usd_rate)
    flags = [*_spec_mismatch(text), *_server_hardware(text, category),
             *_mining(text, category, condition), *_no_lhr(text, category),
             *_used_as_new(text, condition), *_fake_capacity(text, category, price_usd),
             *_noname_psu(row, text, category, price_usd),
             *_price_below_market(price_usd, market_usd)]
    found = {f["type"] for f in flags}
    for risk in row.get("ai_risks") or []:
        if risk == "used_as_new" and condition not in NEW:
            continue                      # honestly marked as used: not a flag
        if risk in AI_TYPES and risk not in found:
            flags.append(_flag(risk, "info", f"ai_{risk}", "ai"))
            found.add(risk)
    return sorted(flags, key=lambda f: -LEVEL_ORDER[f["level"]])
```

# ПРИЛОЖЕНИЕ Б. Основные запросы программного интерфейса (API)

Полный список из 135 запросов с описанием параметров формируется сервером автоматически (Swagger, адрес `/docs`). В таблице @tab:api приведены основные запросы по группам; все адреса начинаются с `/api`.

Таблица: Основные запросы API ALT STORES {#tab:api widths=2,6,6 font=11}
| Метод | Адрес | Назначение |
|---|---|---|
| POST | /auth/register, /auth/login | регистрация (покупатель или продавец), вход, выдача токена JWT |
| GET | /auth/me | текущий пользователь и роль |
| GET | /catalog/products | поиск и фильтры каталога: q, category, price_min, price_max, in_stock, f_<характеристика> |
| GET | /catalog/products/{id} | карточка товара: характеристики, код ИКПУ, предложения, рыночная цена, флаги |
| GET | /catalog/used, /catalog/categories | раздел б/у; категории с ценой «от …» |
| GET | /catalog/barcode/{code} | карточка по подтверждённому штрихкоду |
| GET | /catalog/stores/{id} | страница магазина, филиалы, предложения |
| GET | /market/overview | индексы категорий, самые подешевевшие и подорожавшие товары |
| GET, PUT | /stores/me | профиль магазина продавца |
| POST | /stores/me/branches | добавление филиала |
| POST | /imports, /imports/text | загрузка файла прайса или текста поста |
| GET | /imports/{id} | состояние разбора и строки предпросмотра |
| POST | /imports/{id}/check | пересчёт Anti-Fraud после правки строки |
| POST | /imports/{id}/retry | повторный разбор нераспознанных строк моделью |
| POST | /imports/{id}/publish | публикация загрузки |
| POST | /imports/{id}/undo, /imports/{id}/cancel | отмена опубликованной (7 дней) или неопубликованной загрузки |
| GET, PATCH | /seller/offers, /seller/offers/{id} | «Мои товары», правка предложения |
| PUT | /seller/offers/{id}/stocks | остатки по филиалам |
| POST | /seller/flags/{id}/dispute | оспаривание флага Anti-Fraud |
| GET | /seller/analytics | аналитика продавца: позиции против рынка |
| POST | /seller/stock/operations | документ учёта: приход, продажа, корректировка, выкладка, возврат |
| GET | /seller/stock/journal | журнал движений с фильтрами |
| GET | /seller/barcodes/lookup | поиск товара по штрихкоду |
| GET, POST | /reservations | брони покупателя; создание брони |
| POST | /reservations/{id}/advance | подтверждение, готовность, выдача брони продавцом |
| GET, POST | /chat/conversations | диалоги; новый диалог по товару, сборке или брони |
| POST | /chat/conversations/{id}/messages | сообщение в диалоге |
| GET | /notifications | уведомления кабинета |
| GET, POST | /admin/... | 25 запросов администратора: магазины, жалобы, флаги, фото, исправления, каналы |

# ПРИЛОЖЕНИЕ В. Фрагмент словаря характеристик

Словарь задан в файле `spec_dictionary.py`. Типы значений: «число» — число в одной единице измерения, «выбор» — значение из допустимого списка (пустой список означает открытый перечень с каноническим написанием), «да/нет» — признак. У всех категорий есть также характеристика «бренд». Фрагмент словаря для семи категорий приведён в таблице @tab:dict.

Таблица: Фрагмент словаря характеристик {#tab:dict widths=3,4,3,6 font=11}
| Категория | Ключ | Тип | Единица или допустимые значения |
|---|---|---|---|
| Процессоры | series (линейка) | выбор | Core i3 … i9, Core Ultra 5/7/9, Ryzen 3 … 9, Ryzen AI, Xeon, Apple M1 … M5 и др. |
| | socket (сокет) | выбор | LGA1150, LGA1151, LGA1200, LGA1700, LGA1851, LGA2011, AM4, AM5 и др. |
| | cores, threads | число | ядра, потоки |
| | graphics (встроенная графика) | да/нет | выводится правилом для Intel с буквой F |
| | pack (комплектация) | выбор | BOX, OEM |
| Видеокарты | vendor | выбор | NVIDIA, AMD, Intel (выводится по чипу) |
| | chip | выбор | открытый список: «RTX 4060 Ti», «RX 9070 XT» |
| | memory | число | ГБ |
| | memory_type | выбор | GDDR5, GDDR6, GDDR6X, GDDR7 |
| | revision | выбор | LHR, Full Hash Rate |
| Оперативная память | type | выбор | DDR3, DDR4, DDR5 |
| | form_factor | выбор | DIMM, SODIMM |
| | capacity | число | ГБ, для комплекта — суммарно (2x8GB → 16) |
| | frequency | число | МГц |
| | modules, ecc, rgb | число, да/нет | число планок; ECC; подсветка |
| SSD-накопители | capacity | число | ГБ (ТБ × 1000) |
| | interface, form_factor, pcie | выбор | NVMe, SATA; M.2, 2.5"; 3.0, 4.0, 5.0 |
| Мониторы | size | число | дюймы |
| | resolution, panel | выбор | открытый список; IPS, VA, TN, OLED |
| | refresh_rate | число | Гц, фильтр «от N» |
| Блоки питания | power | число | Вт, фильтр «от N» |
| | certification | выбор | 80 PLUS, White, Bronze, Silver, Gold, Platinum |
| | modular, form_factor | выбор | полностью, частично, нет; ATX, SFX |
| Материнские платы | socket, chipset | выбор | LGA1700, AM5 и др.; открытый список «B760», «X870» |
| | form_factor, memory_type | выбор | E-ATX, ATX, mATX, ITX; DDR3, DDR4, DDR5 |
| | wifi | да/нет | наличие Wi-Fi |

Пример нормализации: строки «16GB», «16 ГБ», «16гб», «2x8GB», «8GB*2» и «16GB (8*2)» дают значение capacity = 16; строки «80+ Gold» и «80 PLUS Gold» — значение certification = Gold; «SO-DIMM» и «SODIM» — form_factor = SODIMM.

# ПРИЛОЖЕНИЕ Г. ER-диаграмма прочих таблиц

![ER-диаграмма: сборки, Telegram-каналы, чат, уведомления, действия администратора](docs/diagrams/er_other.png){#fig:er-other width=16.5}
