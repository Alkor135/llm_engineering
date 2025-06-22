import requests
import json
from typing import List
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from IPython.display import Markdown, display, update_display
from openai import OpenAI

openai = OpenAI(base_url='http://localhost:1234/v1', api_key='google/gemma-3-12b')
MODEL = 'google/gemma-3-12b'

# Класс для представления веб-страницы

# Для некоторых веб-сайтов требуется, чтобы вы использовали правильные заголовки при их загрузке:
headers = {
 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) \
    Chrome/117.0.0.0 Safari/537.36"
}

class Website:
    """
    Служебный класс для представления веб-сайта, который мы скрапим, теперь со ссылками
    """

    def __init__(self, url):
        self.url = url
        response = requests.get(url, headers=headers)
        self.body = response.content
        soup = BeautifulSoup(self.body, 'html.parser')
        self.title = soup.title.string if soup.title else "No title found"
        if soup.body:
            for irrelevant in soup.body(["script", "style", "img", "input"]):
                irrelevant.decompose()
            self.text = soup.body.get_text(separator="\n", strip=True)
        else:
            self.text = ""
        links = [link.get('href') for link in soup.find_all('a')]
        self.links = [link for link in links if link]

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"
    
def get_links_user_prompt(website):
    user_prompt = f"Вот список ссылок на веб-сайте {website.url} - "
    user_prompt += "пожалуйста, решите, какие из них являются релевантными веб-ссылками для \
        брошюры о компании, и укажите полный URL-адрес https в формате JSON. \
        Не указывайте Условия предоставления услуг, конфиденциальность, ссылки на электронную почту.\n"
    user_prompt += "Ссылки (некоторые из них могут быть относительными):\n"
    user_prompt += "\n".join(website.links)
    return user_prompt

def get_links(url):
    website = Website(url)
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": get_links_user_prompt(website)}
      ],
        # response_format={"type": "json_object"}
    )
    result = response.choices[0].message.content
    # print(response.choices[0].message.content)
    # return json.loads(result)
    return result


# link_system_prompt = "Вам будет предоставлен список ссылок, найденных на веб-странице. \
# Вы можете выбрать, какие из ссылок наиболее уместны для включения в брошюру о компании, \
# например, ссылки на страницу О компании, или на страницу Карьера/вакансии.\n"
# link_system_prompt += "Вы должны ответить в формате JSON, как в этом примере:"
# link_system_prompt += """
# {
#     "links": [
#         {"type": "about page", "url": "https://full.url/goes/here/about"},
#         {"type": "careers page": "url": "https://another.full.url/careers"}
#     ]
# }
# """

link_system_prompt = "Вам будет предоставлен список ссылок, найденных на веб-странице. \
Вы можете выбрать, какие из ссылок наиболее уместны для включения в брошюру о компании, \
например, ссылки на страницу О компании, или на страницу Карьера/вакансии.\n"
link_system_prompt += "Вы должны вернуть их в виде JSON-массива строк: "
'{"links": ["url1", "url2", ...]}'
link_system_prompt += """
{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page": "url": "https://another.full.url/careers"}
    ]
}
"""

huggingface = Website("https://huggingface.co")
huggingface.links
print(get_links_user_prompt(huggingface))

hg = get_links("https://huggingface.co")
print(hg)

