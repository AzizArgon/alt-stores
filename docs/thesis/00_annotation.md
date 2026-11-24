# *Аннотация

Выпускная квалификационная работа посвящена разработке информационной системы ALT STORES — единой базы компьютерной техники Узбекистана. Система принимает прайс-листы магазинов в любом виде (Excel, PDF, посты Telegram) и приводит их к эталонным карточкам товаров, чтобы покупатель мог сравнить предложения всех магазинов, а продавец — вести учёт остатков по филиалам. Предложен конвейер «код → кэш → правила → языковая модель», в котором цену, валюту и наличие всегда определяет код. Разработаны ключ сведения товаров, словарь характеристик 31 категории, проверка подозрительных предложений (Anti-Fraud) и мониторинг цен. Эксперимент на 1 178 строках показал 100 % верных цен, 97,2 % моделей и 93,1 % верного сведения; Anti-Fraud нашёл 22 подвоха из 22. Стек: FastAPI, SQLite, React, Docker. Работа содержит 4 главы, ##FIGS##, ##TABS##, ##SRC## и 4 приложения.

# *Abstract

The graduation thesis presents the development of ALT STORES, an information system that forms a single database of computer hardware in Uzbekistan. The system accepts store price lists in any form (Excel, PDF, Telegram posts) and converts them into reference product cards, so that buyers can compare offers from all stores and sellers can keep track of stock across branches. A pipeline "code → cache → rules → language model" is proposed in which price, currency and availability are always determined by code. A product matching key, an attribute dictionary for 31 categories, a check of suspicious offers (Anti-Fraud) and price monitoring were developed. An experiment on 1,178 rows showed 100 % correct prices, 97.2 % models and 93.1 % correct matching; Anti-Fraud caught 22 of 22 traps. Stack: FastAPI, SQLite, React, Docker. The thesis contains 4 chapters, ##EFIGS##, ##ETABS##, ##ESRC## and 4 appendices.

# *Оглавление

[[TOC]]
