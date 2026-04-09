import requests
from bs4 import BeautifulSoup
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
res = requests.post("https://lite.duckduckgo.com/lite/", data={"q": "latest news Stafford UK"}, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")

results = []
for tr in soup.find_all('tr'):
    result_snippet = tr.find('td', class_='result-snippet')
    if result_snippet:
        prev_tr = tr.find_previous_sibling('tr')
        if prev_tr:
            a_tag = prev_tr.find('a', class_='result-title') # usually class isn't result-url but result-title... wait let's just find the first 'a' in the previous tr
            if not a_tag:
                a_tag = prev_tr.find('a')
            if a_tag:
                results.append({
                    "title": a_tag.text.strip(),
                    "body": result_snippet.text.strip(),
                    "href": a_tag.get('href', "")
                })

print(json.dumps(results[:3], indent=2))
