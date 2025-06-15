# install the library first if you haven't: pip install beautifulsoup4 lxml
from bs4 import BeautifulSoup

# --- EDIT THIS LINE ---
html_file_path = '/mnt/caseSSD/mcp_server_project/vLLM_guide_medium.html' # <-- Put the name of your local file here

try:
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'lxml')

    # Try to find the main article tag, a common standard
    article_body = soup.find('article')

    # If <article> isn't found, try common div classes for content
    if not article_body:
        # You can add more potential class names to this list
        potential_classes = ['post-content', 'article-body', 'main-content', 'entry-content']
        for class_name in potential_classes:
            article_body = soup.find('div', class_=class_name)
            if article_body:
                break # Stop when we find one

    # If still not found, just get all the text from the body
    if not article_body:
        article_body = soup.find('body')

    if article_body:
        article_text = article_body.get_text(separator='\n', strip=True)
        print(article_text)
    else:
        print("Could not find any content.")

except FileNotFoundError:
    print(f"Error: File not found at '{html_file_path}'")