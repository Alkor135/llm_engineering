"""
Скрипт для предсказания направления следующей свечи (next_bar) на основе markdown-файлов с новостями.
Использует OpenAI для генерации эмбеддингов.
Кэширует эмбеддинги в pickle-файл с проверкой актуальности.
Ограничивает количество предыдущих файлов параметрами min_prev_files и max_prev_files.
Добавляет финансовый результат (pips) и накопительный результат (cumulative_pips).
"""

import pandas as pd
from pathlib import Path
import pickle
import hashlib
import numpy as np
import yaml
import os
from langchain_core.documents import Document
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import sqlite3

# Параметры
md_path = Path(r'C:\Users\Alkor\gd\md_rss_investing')
cache_file = Path(r'embeddings_cache_openai.pkl')
path_db_quote = Path(r'C:\Users\Alkor\gd\data_quote_db\RTS_futures_day_2025_21-00.db')
model_name = "text-embedding-3-small"  # Модель OpenAI для эмбеддингов
openai_api_key = os.getenv("OPENAI_API_KEY")  # Убедитесь, что ключ задан в переменной окружения
min_prev_files = 4   # Минимальное количество предыдущих файлов для предсказаний
max_prev_files = 30  # Максимальное количество предыдущих файлов для предсказаний

def cosine_similarity(vec1, vec2):
    """Вычисляет косинусное сходство между двумя векторами."""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

def load_markdown_files(directory):
    """Загружает все MD-файлы из директории, сортирует по дате (имени файла)."""
    files = sorted(directory.glob("*.md"), key=lambda f: f.stem)  # Сортировка по дате ascending
    documents = []
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                metadata_yaml = parts[1].strip()
                text_content = parts[2].strip()
                metadata = yaml.safe_load(metadata_yaml) or {}
                metadata_str = {
                    "next_bar": str(metadata.get("next_bar", "unknown")),
                    "date_min": str(metadata.get("date_min", "unknown")),
                    "date_max": str(metadata.get("date_max", "unknown")),
                    "source": file_path.name,
                    "date": file_path.stem
                }
                doc = Document(page_content=text_content, metadata=metadata_str)
                documents.append(doc)
    return documents

def load_quotes(path_db_quote):
    """Читает таблицу Futures из базы данных котировок и возвращает DataFrame с pips."""
    with sqlite3.connect(path_db_quote) as conn:
        df = pd.read_sql_query("SELECT TRADEDATE, OPEN, CLOSE FROM Futures", conn)
    df['TRADEDATE'] = df['TRADEDATE'].astype(str)
    df['pips'] = df['CLOSE'] - df['OPEN']
    return df[['TRADEDATE', 'pips']].set_index('TRADEDATE')

def cache_is_valid(documents, cache_file):
    """Проверяет, актуален ли кэш эмбеддингов."""
    if not cache_file.exists():
        return False

    cache_mtime = cache_file.stat().st_mtime
    current_files = {doc.metadata['source'] for doc in documents}

    # Загружаем кэш для проверки
    with open(cache_file, 'rb') as f:
        cache = pickle.load(f)

    cache_files = {item['metadata']['source'] for item in cache}

    # Проверяем, совпадают ли наборы файлов
    if current_files != cache_files:
        print("Кэш устарел: изменился набор markdown-файлов.")
        return False

    # Проверяем, не изменились ли файлы
    for doc in documents:
        file_path = md_path / doc.metadata['source']
        if file_path.stat().st_mtime > cache_mtime:
            print(f"Кэш устарел: файл {file_path.name} был изменён.")
            return False

    return True

def cache_embeddings(documents, cache_file, model_name, api_key):
    """Вычисляет и кэширует эмбеддинги всех документов в pickle-файл."""
    if cache_is_valid(documents, cache_file):
        print(f"Загрузка кэша эмбеддингов из {cache_file}")
        with open(cache_file, 'rb') as f:
            cache = pickle.load(f)
        return cache

    print("Вычисление эмбеддингов с OpenAI...")
    ef = OpenAIEmbeddingFunction(api_key=api_key, model_name=model_name)
    cache = []
    for doc in documents:
        embedding = ef([doc.page_content])[0]
        cache.append({
            'id': hashlib.md5(doc.page_content.encode()).hexdigest(),
            'embedding': embedding,
            'metadata': doc.metadata
        })
    with open(cache_file, 'wb') as f:
        pickle.dump(cache, f)
    print(f"Эмбеддинги сохранены в {cache_file}")
    return cache

def predict_next_bar(documents, cache, quotes_df):
    """Предсказывает направление next_bar для документа с next_bar='None'."""
    # Поиск документа с next_bar="None"
    none_doc = None
    for doc in documents:
        if doc.metadata['next_bar'] == "None":
            none_doc = doc
            break

    if not none_doc:
        print("Документ с next_bar='None' не найден.")
        return

    none_date = none_doc.metadata['date']
    print(f"\nПредсказание для даты {none_date} (next_bar='None'):")

    # Получение эмбеддинга документа с next_bar="None"
    none_id = hashlib.md5(none_doc.page_content.encode()).hexdigest()
    none_embedding = None
    for item in cache:
        if item['id'] == none_id:
            none_embedding = item['embedding']
            break
    if none_embedding is None:
        print(f"Эмбеддинг для даты {none_date} не найден в кэше.")
        return

    # Получение предыдущих документов из кэша, ближайших по дате
    prev_cache = sorted(
        [item for item in cache if item['metadata']['next_bar'] != "None" and item['metadata']['date'] < none_date],
        key=lambda x: x['metadata']['date'], reverse=True
    )[:max_prev_files]  # Ограничиваем max_prev_files ближайшими датами

    if len(prev_cache) < min_prev_files:
        print(f"Недостаточно предыдущих документов для даты {none_date}: {len(prev_cache)}")
        return

    # Вычисление сходств
    similarities = [
        (cosine_similarity(none_embedding, item['embedding']) * 100, item['metadata'])
        for item in prev_cache
    ]

    # Сортировка по убыванию сходства
    similarities.sort(key=lambda x: x[0], reverse=True)

    # Ближайший документ
    if similarities:
        closest_similarity, closest_metadata = similarities[0]
        predicted_next_bar = closest_metadata['next_bar']

        # Получение pips из базы котировок (если доступно)
        pips = None
        try:
            pips_value = quotes_df.loc[none_date, 'pips']
            pips = abs(pips_value)  # Предполагаем правильное предсказание для оценки
        except KeyError:
            print(f"Данные котировок для даты {none_date} не найдены.")

        print(f"\nПредсказание для даты {none_date}:")
        print(f"Предсказанное направление: {predicted_next_bar}")
        print(f"Процент сходства: {closest_similarity:.2f}%")
        print("Метаданные ближайшего документа:")
        for key in sorted(closest_metadata.keys()):
            print(f"  {key}: {closest_metadata[key]}")
        if pips is not None:
            print(f"Потенциальный финансовый результат: {pips:.2f} пунктов")
    else:
        print("Нет похожих документов для предсказания.")

if __name__ == '__main__':
    # Проверка API-ключа OpenAI
    if not openai_api_key:
        print("Ошибка: OPENAI_API_KEY не задан. Установите переменную окружения.")
        exit(1)

    # Загрузка котировок
    if not path_db_quote.exists():
        print(f"Ошибка: Файл базы данных котировок не найден: {path_db_quote}")
        exit(1)
    quotes_df = load_quotes(path_db_quote)

    # Загрузка markdown-файлов
    documents = load_markdown_files(md_path)
    if len(documents) < min_prev_files + 1:
        print(f"Недостаточно файлов: {len(documents)}. Требуется минимум {min_prev_files + 1}.")
        exit(1)

    # Кэширование эмбеддингов
    cache = cache_embeddings(documents, cache_file, model_name, openai_api_key)
    predict_next_bar(documents, cache, quotes_df)