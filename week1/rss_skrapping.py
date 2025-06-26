import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import time


def get_links(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Найти заголовок "Новости"
    news_section = soup.find('h2', string='Новости')

    if news_section:
        # Найти родительский div с нужными классами
        rss_column = news_section.find_parent('div',
                                              class_='rssColumn halfSizeColumn float_lang_base_2')

        if rss_column:
            # Найти ul с классом "rssBox" внутри этого div
            rss_box = rss_column.find('ul', class_='rssBox')

            if rss_box:
                # Найти все элементы <li> внутри ul
                list_items = rss_box.find_all('li')

                # Извлечь ссылки из каждого li и отфильтровать по расширению ".rss"
                rss_links = []
                for item in list_items:
                    a_tag = item.find('a')
                    if a_tag and a_tag.get('href') and a_tag['href'].endswith('.rss'):
                        rss_links.append(a_tag['href'])

                # # Вывести результаты
                # for link in rss_links:
                #     print(link)
                return rss_links

            else:
                print("Список RSS не найден.")
        else:
            print("Контейнер с новостями не найден.")
    else:
        print("Раздел 'Новости' не найден.")

def parsing_news(rss_links):
    df = pd.DataFrame(columns=["Дата", "Раздел", "Заголовок", "Ссылка"])
    for rss_link in rss_links:
        try:
            response = requests.get(rss_link)
            response.raise_for_status()  # Проверка на ошибки HTTP (например, 404)

            xml_content = response.text

            root = ET.fromstring(xml_content)

            channel = root.find('.//channel')  # Находим тег <channel>
            channel_name = ''
            if channel is not None: # Добавляем проверку на None
                # Получаем текст напрямую из найденного канала
                channel_name = channel.find('title').text 
                print(channel_name)

            # Теперь вы можете перебирать элементы XML
            for item in root.findall('.//item'): # Находим все теги <item>
                title = item.find('title').text if item.find('title') is not None else "Нет заголовка"
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "Нет даты публикации"
                link = item.find('link').text if item.find('link') is not None else "Нет ссылки"

                # print(f'{pub_date} {channel_name} {title} {link}')
                df.loc[len(df)] = [pub_date, channel_name, title, link]

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к URL: {e}")
        except ET.ParseError as e:
            print(f"Ошибка при парсинге XML: {e}")
        time.sleep(1)
    return df

# def add_article_text(df):
#     news_texts = []
#     for url in df["Ссылка"]:
#         try:
#             print(url)
#             response = requests.get(url, timeout=10)
#             response.raise_for_status()
#             soup = BeautifulSoup(response.text, "html.parser")
#             article_div = soup.find("div", id="article", class_="article_container")
#             if article_div:
#                 # Получаем только текст без HTML-тегов
#                 news_texts.append(article_div.get_text(separator="\n", strip=True))
#             else:
#                 news_texts.append("Текст статьи не найден")
#         except Exception as e:
#             news_texts.append(f"Ошибка: {e}")
#         # time.sleep(1)
#     df["Новость"] = news_texts
#     return df

def drop_duplicate_titles(df):
    """
    Удаляет дубликаты по полю 'Заголовок', оставляя первую строку с самой ранней датой.
    """
    # Преобразуем поле "Дата" в datetime для корректной сортировки
    df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")
    # Сортируем по "Заголовок" и "Дата" (по возрастанию даты)
    df_sorted = df.sort_values(by=["Заголовок", "Дата"])
    # Оставляем только первое вхождение каждого заголовка
    df_unique = df_sorted.drop_duplicates(subset=["Заголовок"], keep="first")
    # Восстанавливаем исходный порядок индексов
    df_unique = df_unique.sort_index()
    return df_unique

if __name__ == '__main__':
    URL = "https://ru.investing.com/webmaster-tools/rss"

    rss_links = get_links(URL)
    print(rss_links)
    df = parsing_news(rss_links)
    print(df[["Заголовок", "Ссылка"]])
    # df[["Заголовок", "Ссылка"]].to_csv("rss_links.txt", sep=";", index=False)

    # df = add_article_text(df)
    # print(df[["Заголовок", "Ссылка", "Новость"]].head())
    # df[["Заголовок", "Ссылка", "Новость"]].to_csv("rss_links.txt", sep=";", index=False)

    df = drop_duplicate_titles(df)
    print(df[["Дата", "Заголовок"]])
    df[["Заголовок"]].to_csv("rss_links.txt", sep=";", index=False)
