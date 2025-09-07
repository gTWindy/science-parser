import json
import pandas as pd
from io import BytesIO
from typing import List, Dict, Any, Union

class DataSerializer:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data
    
    def to_json(self, indent: int = 2) -> str:
        """Сериализация в JSON"""
        return json.dumps(self.data, indent=indent, ensure_ascii=False)
    
    def to_excel(self, filename: str = "output.xlsx") -> BytesIO:
        """Сериализация в Excel"""
        df = pd.DataFrame(self.data)
        
        # Сохраняем в BytesIO для возврата как файл
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
        
        output.seek(0)
        return output
    
    def serialize(self, format_type: str, **kwargs) -> Union[str, BytesIO]:
        """Основной метод сериализации"""
        format_type = format_type.lower()
        
        if format_type == 'json':
            return self.to_json(**kwargs)
        elif format_type == 'excel':
            return self.to_excel(**kwargs)
        else:
            raise ValueError(f"Unsupported format: {format_type}. Use 'json' or 'excel'")

# Пример использования
if __name__ == "__main__":
    # Пример данных
    data = [
        {"id": 1, "name": "John", "age": 25, "city": "New York"},
        {"id": 2, "name": "Alice", "age": 30, "city": "London"},
        {"id": 3, "name": "Bob", "age": 35, "city": "Tokyo"}
    ]
    
    serializer = DataSerializer(data)
    
    # Пользователь выбирает формат
    user_choice = input("Выберите формат (json/excel): ").strip().lower()
    
    try:
        if user_choice == 'json':
            result = serializer.serialize('json')
            print("JSON результат:")
            print(result)
            
        elif user_choice == 'excel':
            result = serializer.serialize('excel')
            
            # Сохраняем файл
            filename = input("Введите имя файла (по умолчанию output.xlsx): ") or "output.xlsx"
            with open(filename, 'wb') as f:
                f.write(result.getvalue())
            print(f"Файл сохранен как {filename}")
            
        else:
            print("Неверный выбор. Используйте 'json' или 'excel'")
            
    except Exception as e:
        print(f"Ошибка: {e}")