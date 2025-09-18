import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum, auto

class ParserErrorType(Enum):
    # Общие ошибки
    JSON_DECODE_ERROR = auto()
    MISSING_REQUIRED_FIELD = auto()
    UNEXPECTED_ERROR = auto()
    
    # Ошибки полей
    INVALID_ISSN_FORMAT = auto()
    INVALID_ISSN_CHECKSUM = auto()
    EMPTY_KEYWORDS_LIST = auto()
    INVALID_KEYWORD_TYPE = auto()
    INVALID_RESOURCE_TYPE = auto()
    EMPTY_RESOURCES_LIST = auto()
    
    # Ошибки дат
    INVALID_DATE_FORMAT = auto()
    INVALID_MONTH = auto()
    INVALID_YEAR = auto()
    DATE_RANGE_INVALID = auto()  # time_from > time_to
    
    # Структурные ошибки
    INVALID_FIELD_TYPE = auto()
    INVALID_TIME_PERIOD_STRUCTURE = auto()

@dataclass
class ParserError:
    error_type: ParserErrorType
    message: str
    field_name: Optional[str] = None
    value: Any = None
    
    def __str__(self):
        if self.field_name:
            return f"{self.error_type.name}: {self.message} (поле: {self.field_name}, значение: {self.value})"
        return f"{self.error_type.name}: {self.message}"

@dataclass
class SearchCriteria:
    journals_issn: List[str]
    keywords: List[str]
    time_from: str
    time_to: str
    check_pirate_resources: bool

class SearchCriteriaParser:
    def __init__(self):
        self.validation_errors: List[ParserError] = []
    
    def getErrors(self) -> List[ParserError]:
        return self.validation_errors

    def parse_json(self, json_data: str) -> Optional[SearchCriteria]:
        try:
            data = json.loads(json_data)
            return self.parse_dict(data)
        except json.JSONDecodeError as e:
            self._add_error(
                ParserErrorType.JSON_DECODE_ERROR,
                f"Ошибка парсинга JSON: {e}"
            )
            return None
        except Exception as e:
            self._add_error(
                ParserErrorType.UNEXPECTED_ERROR,
                f"Неожиданная ошибка: {e}"
            )
            return None
    
    # Добавляет ошибку в список
    def _add_error(self, error_type: ParserErrorType, message: str, 
                   field_name: Optional[str] = None, value: Any = None):
        self.validation_errors.append(
            ParserError(error_type, message, field_name, value)
        )
    
    def parse_dict(self, data: Dict[str, Any]) -> Optional[SearchCriteria]:
        try:
            # Валидация обязательных полей
            if not self._validate_required_fields(data):
                return None
            
            # Парсинг и валидация отдельных полей
            journals_issn = self._parse_journals_issn(data['journals_issn'])
            keywords = self._parse_keywords(data['keywords'])
            time_from = self._parse_date(data['time_from'], 'time_from')
            time_to = self._parse_date(data['time_to'], 'time_to')
            check_pirate_resources = self._parse_resources(data['check_pirate_resources'])
            
            # Проверка временного диапазона
            if time_from and time_to and time_from > time_to:
                self._add_error(
                    ParserErrorType.DATE_RANGE_INVALID,
                    "Начальная дата не может быть больше конечной",
                    None,
                    f"{time_from} > {time_to}"
                )

            if self.validation_errors:
                return None
            
            return SearchCriteria(
                journals_issn=journals_issn,
                keywords=keywords,
                time_from=time_from,
                time_to=time_to,
                check_pirate_resources=check_pirate_resources
            )
            
        except KeyError as e:
            self._add_error(
                ParserErrorType.MISSING_REQUIRED_FIELD,
                f"Отсутствует обязательное поле",
                str(e)
            )
            return None
    
    # Проверяет наличие всех полей
    def _validate_required_fields(self, data: Dict[str, Any]) -> bool:
        required_fields = ['journals_issn', 'keywords', 'time_from','time_to', 'check_pirate_resources']
        missing_fields = []
        
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            for field in missing_fields:
                self._add_error(
                    ParserErrorType.MISSING_REQUIRED_FIELD,
                    "Отсутствует обязательное поле",
                    field
                )
            return False
        return True
    
    # Парсит и валидирует ISSN
    def _parse_journals_issn(self, issn_data_list: Any) -> List[str]:
        if not isinstance(issn_data_list, List):
            self._add_error(
                ParserErrorType.INVALID_FIELD_TYPE,
                "Поле должно быть списком строк",
                "journals_issn",
                type(issn_data_list).__name__
            )
            return ""
        
        for issn_data in issn_data_list:
            issn = issn_data.strip()
            if not issn:
                return []
            
            # Проверка формата
            if not re.match(r'^\d{4}-\d{3}[\dX]$', issn):
                self._add_error(
                    ParserErrorType.INVALID_ISSN_FORMAT,
                    "Неверный формат ISSN. Ожидается XXXX-XXXX",
                    "journals_issn",
                    issn
                )
                return issn_data_list
            
            # Проверка контрольной суммы
            if not self._validate_issn_checksum(issn):
                self._add_error(
                    ParserErrorType.INVALID_ISSN_CHECKSUM,
                    "Неверная контрольная сумма ISSN",
                    "journals_issn",
                    issn
                )
            
        return issn_data_list

    # Проверяет контрольную сумму ISSN
    def _validate_issn_checksum(self, issn: str) -> bool:
        digits = issn.replace('-', '')
        total = 0
        for i, char in enumerate(digits):
            digit = 10 if char.upper() == 'X' else int(char)
            total += digit * (8 - i)
        return total % 11 == 0
    
    # Парсит ключевые слова
    def _parse_keywords(self, keywords_data: Any) -> List[str]:
        if not isinstance(keywords_data, list):
            self.validation_errors.append("Поле 'ключевые слова' должно быть списком")
            return []
        
        keywords = []
        for i, keyword in enumerate(keywords_data):
            if not isinstance(keyword, str):
                self.validation_errors.append(f"Ключевое слово #{i+1} должно быть строкой")
                continue
            
            cleaned_keyword = keyword.strip()
            if cleaned_keyword:
                keywords.append(cleaned_keyword)
        
        if not keywords:
            self.validation_errors.append("Список ключевых слов не может быть пустым")
        
        return keywords
    
    def _parse_date(self, date_data: Any, field_name: str) -> str:
        if not isinstance(date_data, str):
            self._add_error(
                ParserErrorType.INVALID_FIELD_TYPE,
                "Поле даты должно быть строкой",
                field_name,
                type(date_data).__name__
            )
            return ""
        
        date_str = date_data.strip()
        if not date_str:
            return ""
        
        # Проверка формата YYYY-MM
        if not re.match(r'^\d{4}-\d{2}$', date_str):
            self._add_error(
                ParserErrorType.INVALID_DATE_FORMAT,
                "Неверный формат даты. Ожидается YYYY-MM",
                field_name,
                date_str
            )
            return date_str
        
        try:
            year, month = map(int, date_str.split('-'))
            if month < 1 or month > 12:
                self._add_error(
                    ParserErrorType.INVALID_MONTH,
                    "Месяц должен быть от 01 до 12",
                    field_name,
                    date_str
                )
            
            current_year = datetime.now().year
            if year < 1900 or year > current_year + 5:
                self._add_error(
                    ParserErrorType.INVALID_YEAR,
                    f"Год должен быть между 1900 и {current_year + 5}",
                    field_name,
                    date_str
                )
            
        except ValueError:
            self._add_error(
                ParserErrorType.INVALID_DATE_FORMAT,
                "Неверный формат даты",
                field_name,
                date_str
            )
        
        return date_str
    
    # Проверяет параметр проверки пиратских ресурсов
    def _parse_resources(self, resources_data: Any) -> bool:
        if not isinstance(resources_data, bool):
            self.validation_errors.append("Поле 'Проверять пиратские ресурсы' должно быть булевым значением")
            return False
            
        return resources_data

# Тесты
def test():
    breakpoint()
    # Тест 1
    test_json = '{"journals_issn": "1234", "keywords": ["test"]}'
    parser = SearchCriteriaParser()
    result = parser.parse_json(test_json)
    assert result is None
    assert "Отсутствуют обязательные поля" in parser.get_validation_errors()[0]
    
    # Тест 2
    test_json2 = '{"journals_issn": "1234", "keywords": ["test"], "time_from": "2020-01", "time_to": "2023-12", "check_pirate_resources": False}'
    result2 = parser.parse_json(test_json2)
    assert result2 is None
    print("Все тесты пройдены! ✅")

if __name__ == "__main__":
    test()