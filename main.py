import requests
import sys
import urllib.parse
from datetime import datetime
import asyncio
import aiohttp

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

async def main(keywords, max_results=10):
    url = "https://api.crossref.org/works"
    journal = "issn:1939-0122"
    
    query = " OR ".join(keywords)

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
    print(f"Ищем статьи по ключевым словам: {', '.join(keywords)}")

    try:
        data = await fetch_crossref_data(url, params, headers, 20)

        # Останавливаем анимацию
        animation_task.cancel()

        articles = data['message']['items']

        print(f"\nНайдено статей: {len(articles)}")
        print("-" * 50)

        for i, article in enumerate(articles, 1):
            title = article.get('tittle', ['Без названия'])[0]
            authors = article.get('author', [])
            author_names = [f"{a.get('given', '')} {a.get('family', '')}" for a in authors[:2]]

            print(f"{i}. {title}")
            print(f"   Авторы: {', '.join(author_names)}")
            if 'DOI' in article:
                print(f"   DOI: {article['DOI']}")
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
        keywords = sys.argv[1:]
        articles = asyncio.run(main(keywords, max_results=5))
    else:
        print("Пока не сделано")