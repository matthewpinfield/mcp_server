import requests
import json
import time

url = "http://localhost:8013/api/chat"
headers = {"Content-Type": "application/json"}
data = {
    "model": "gemma4:26b",
    "messages": [{"role": "user", "content": "Search the web and provide me with 3 bullet points summarizing the contents of example.com"}],
    "stream": True
}

start_time = time.time()
first_token_time = None
chunks = 0

with requests.post(url, headers=headers, json=data, stream=True) as response:
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data: "):
                data_str = decoded_line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    payload = json.loads(data_str)
                    content = payload["choices"][0]["delta"].get("content", "")
                    if content and not first_token_time:
                        first_token_time = time.time()
                        print(f"Time to First Token: {first_token_time - start_time:.2f} seconds")
                    if content:
                        chunks += 1
                        print(content, end="", flush=True)
                except Exception as e:
                    pass

end_time = time.time()
print(f"\n\nTotal Stream Time: {end_time - start_time:.2f} seconds")
print(f"Total Chunks: {chunks}")
