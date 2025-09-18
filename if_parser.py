import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def if_parser(journal_name_list: dict):
    if_list = {}
    for issn, journal_name in journal_name_list.items():
        # Получаем HTML страницы
        url = 'https://www.wiley.com/en-us/journals/'+journal_name
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text
        except requests.exceptions.HTTPError as e:
            print(f"\nHTTP ошибка: {e}")
            print(f"Устанавливаем импакт фактор равным -1")
            if_list[issn] = -1
            continue
        except requests.exceptions.Timeout as e:
            print(f"Таймаут для {journal_name}: {e}")
            if_list[issn] = -1
            continue
        except Exception as e:
            print(f"Неожиданная ошибка для {journal_name}: {e}")
            if_list[issn] = -1
            continue
        # Парсим HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        try:
            # Найти элемент по классу
            elements = soup.find_all('div', class_='text-piped')
            impact_factor = elements[0].contents[2].contents[0].split()[2]
            if_list[issn] = float(impact_factor)
        except:
            print("Содержимое сайта поменялась, свяжитесь с автором программы")
            break
    return if_list
