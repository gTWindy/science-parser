import sys
import urllib.parse
from datetime import datetime
import asyncio
import aiohttp
import json
from enum import Enum
from dataclasses import dataclass

from json_parser import SearchCriteriaParser
from serializer import DataSerializer
from if_parser import if_parser


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

@dataclass
class Article:
    issn: str
    authors: tuple[str]
    title: str
    doi: str
    access: str
    journal_title: str
    journal_issn: str
    impact_factor: float
    pirate_resource: str = "Без поиска"

    # Преобразует объект Article в словарь
    def to_dict(self):
        return {
            'issn': self.issn,
            'authors': self.authors,
            'title': self.title,
            'access': self.access,
            'pirate_resource': self.pirate_resource,
            'impact_factor': self.impact_factor
        }

# Анализ лицензии Wiley по URL
def analyze_wiley_license_url(license_url: str) -> str:
    if not license_url:
        return LicenseType.UNKNOWN.value
    
    url_lower = license_url.lower()
    
    # Creative Commons = БЕСПЛАТНО
    if "creativecommons.org" in url_lower:
        return LicenseType.FREE.value
        
    # Wiley Terms = ПЛАТНО
    elif "wiley.com" in url_lower and ("terms" in url_lower or "copyright" in url_lower):
        return LicenseType.NOT_FREE.value
    
    # Другие признаки платного доступа
    elif any(x in url_lower for x in ["rights-and-permissions", "subscription", "copyright"]):
        return LicenseType.NOT_FREE.value
    
    # Другие открытые лицензии
    elif any(x in url_lower for x in ["publicdomain", "pd", "cc0"]):
        return LicenseType.FREE.value
    
    # Если не смогли определить - предполагаем платное
    else:
        return LicenseType.NOT_FREE.value

# Проверяет доступность статьи на Sci-Hub
async def check_sci_hub(session, doi: str) -> str:
    if not doi or doi == "Не найдено":
        return "Doi не найдено"
    try:
        async with session.get(f'https://sci-hub.ru/{doi}', timeout=100) as response:
            content = await response.text()
            return 'Найдено' if 'Не найдено' not in content else 'Не найдено'
    except Exception as e:
        print(f"Ошибка при проверке DOI {doi}: {e}")
        return "Ошибка"
    except asyncio.TimeoutError:
        print(f"Таймаут при проверке DOI {doi}")
        return "Таймаут"

async def process_articles(pirate_resources, crossref_response):
    data_articles = []
    journal_fullname = {}

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, article in enumerate(crossref_response):
            title = article.get('title', ['Без названия. Название не найдено'])[0]
            authors = article.get('author', [])
            author_names = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors[:2]]
            license = analyze_wiley_license_url(article.get('license', [{"URL": 'unknown'}])[0]["URL"])
            journal_title = article.get('container-title', [''])[0]
            journal_issn = article.get('ISSN', ['not-found-print-issn', 'not-found-online-issn'])[1]
            doi = article.get('DOI', "Не найдено")
            
            article_obj = Article(
                issn=journal_issn,
                title=title,
                authors=author_names,
                access=license,
                journal_title=journal_title,
                journal_issn=journal_issn,
                doi=doi,
                pirate_resource='Не проверено',
                impact_factor=-1
            )
            data_articles.append(article_obj)
            if journal_issn not in journal_fullname:
                journal_fullname[journal_issn] = f'{journal_title.replace(" ", "+")}-p-{journal_issn.replace("-", "")}'
            if len(pirate_resources) > 0 and license != LicenseType.FREE:
                task = asyncio.create_task(check_sci_hub(session, doi))
                tasks.append((article_obj, task))

        # Ждем завершения всех запросов
        for article_obj, task in tasks:
            pirate_result = await task
            article_obj.pirate_resource = pirate_result

    if_by_journal = if_parser(journal_fullname)
    
    for article in data_articles:
        article.impact_factor = if_by_journal[article.journal_issn]

    return data_articles

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
    
    filter = ""
    if (criteria.journals_issn):
        filter_parts = list(map(lambda issn: f"issn:{issn}", criteria.journals_issn))
        filter = ",".join(filter_parts)
    else:
        # 311 id у издательства Wiley в crossref
        filter = f'member:311,type:journal-article'

    query = " OR ".join(criteria.keywords)

    params = {
        'query': query,
        #'rows': max_results,
        'filter': filter
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

    if len(criteria.pirate_resources) > 0:
        print("На данный момент у нас только один ресурс Sci-Hub")
    else:
        print("Проверка наличия на пиратских ресурсах не проведется")

    try:
        data = await fetch_crossref_data(url, params, headers, 20)

        articles_response = data['message']['items']
        articles_count = len(articles_response)
    
        data_articles = await process_articles(criteria.pirate_resources, articles_response)
        
        # Останавливаем анимацию
        animation_task.cancel()

        print(f"\nНайдено статей: {articles_count}")
        
        while(True):
            char = input("Для загрузки статей введите - j, для загрузки в excel таблицу - e, чтобы просто вывести - p: ")
            if char not in ('j', 'e', 'p'):
                continue
            
            data_for_serialization = [article.to_dict() for article in data_articles]
    
            if char == 'j':
                json_data = DataSerializer(data_for_serialization).to_json()
                with open('output.json', 'w', encoding='utf-8') as f:
                    f.write(json_data)
                print("Данные сохранены в output.json")
                break
                
            elif char == 'e':
                excel_data = DataSerializer(data_for_serialization).to_excel()
                with open('output.xlsx', 'wb') as f:
                    f.write(excel_data.getvalue())
                print("Данные сохранены в output.xlsx")
                break
            
            else:
                for i, article in enumerate(data_articles):
                    print(f"{i}. {article.title}")
                    print(f"   Авторы: {', '.join(article.authors)}")
                    print(f"   DOI: {article.doi}")
                    print(f"access: {article.access}")
                    print(f"pirate: {article.pirate_resource}")
                    print(f"IF: {article.impact_factor}")
                    print("-" * 50)
                break                
        return 0

    except asyncio.TimeoutError as e:
            print(f"Таймаут : {e}")
            return 1
    except Exception as e:
        print(f"\nНеожиданная ошибка: {e}")
        return []

# Запускаем парсер
if __name__ == "__main__":
    if len(sys.argv) > 1:
        max_result = sys.argv[1:1]
        asyncio.run(main(max_results=5))
    else:
        asyncio.run(main(max_results=5))