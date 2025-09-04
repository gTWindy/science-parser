import requests
import sys
import urllib.parse
from datetime import datetime
import asyncio
import aiohttp
import json
from enum import Enum

from json_parser import SearchCriteriaParser

filename = "config.json"

async def show_animation():
    frames = ['.', '..', '...', '.. \b', '. \b']
    i = 0
    start_time = datetime.now()

    while True:
        elapsed = (datetime.now() - start_time).total_seconds()
        sys.stdout.write(f'\r{elapsed:.1f}сек. Загрузка данных{frames[i]}')
        sys.stdout.flush()
        i = (i + 1) % len(frames)
        await asyncio.sleep(0.3)

async def fetch_crossref_data(url, params, headers, timeout = 10):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=timeout) as response:
            return await response.json()

class LicenseType(Enum):
    NOT_FREE = 'NOT FREE'
    FREE = 'FREE'
    UNKNOWN = 'UNKNOWN'

# Анализ лицензии Wiley по URL
def analyze_wiley_license_url(license_url: str) -> LicenseType:
    if not license_url:
        return LicenseType.UNKNOWN
    
    url_lower = license_url.lower()
    
    # Creative Commons = БЕСПЛАТНО
    if "creativecommons.org" in url_lower:
        return LicenseType.FREE
        
    # Wiley Terms = ПЛАТНО
    elif "wiley.com" in url_lower and ("terms" in url_lower or "copyright" in url_lower):
        return LicenseType.NOT_FREE
    
    # Другие признаки платного доступа
    elif any(x in url_lower for x in ["rights-and-permissions", "subscription", "copyright"]):
        return LicenseType.NOT_FREE
    
    # Другие открытые лицензии
    elif any(x in url_lower for x in ["publicdomain", "pd", "cc0"]):
        return LicenseType.FREE
    
    # Если не смогли определить - предполагаем платное
    else:
        return LicenseType.NOT_FREE

async def main(max_results=10):
    data_json = None
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data_json = file.read()
    except FileNotFoundError:
        print(f"Файл {filename} не найден")
        return None
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON: {e}")
        return None

    parser = SearchCriteriaParser()
    print(data_json)
    criteria = parser.parse_json(data_json)
    errors = parser.getErrors()
    if errors:
        for i, error in enumerate(errors):
            print(error)
        return 1

    url = "https://api.crossref.org/works"
    journal = f'issn:{criteria.journal_issn}'

    query = " OR ".join(criteria.keywords)

    params = {
        'query': query,
        #'rows': max_results,
        'filter': journal
    }

    headers = {
        'User-Agent': 'SimpleParser/1.0 (mailto:example@example.com)'
    }

    animation_task = asyncio.create_task(show_animation())

    # Формируем полный URL для логов
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    print(f"Полный URL запроса: {full_url}")
    print(f"Ищем статьи по ключевым словам: {', '.join(criteria.keywords)}")

    try:
        data = await fetch_crossref_data(url, params, headers, 20)

        # Останавливаем анимацию
        animation_task.cancel()

        articles = data['message']['items']

        print(f"\nНайдено статей: {len(articles)}")
        print("-" * 50)

        for i, article in enumerate(articles):
            title = article.get('title', ['Без названия. Название не найдено'])[0]
            authors = article.get('author', [])
            author_names = [f"{a.get('given', '')} {a.get('family', '')}" for a in authors[:2]]
            license = article.get('license', [{url: 'unknown'}])[0]["URL"]

            print(f"{i}. {title}")
            print(f"   Авторы: {', '.join(author_names)}")
            if 'DOI' in article:
                print(f"   DOI: {article['DOI']}")
            print(f"access: {str(analyze_wiley_license_url(license))}")
            print("-" * 50)

        return articles

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе: {e}")
        return []
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return []

# Запускаем парсер
if __name__ == "__main__":
    if len(sys.argv) > 1:
        max_result = sys.argv[1:1]
        articles = asyncio.run(main(max_results=5))
    else:
        articles = asyncio.run(main(max_results=5))