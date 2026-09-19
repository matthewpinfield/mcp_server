import requests
import json

url = "http://localhost:8013/api/chat"
headers = {"Content-Type": "application/json"}
data = {
    "model": "gemma4:26b",
    "messages": [
        {"role": "user", "content": "Hello, my top secret word is 'Giraffe'. Please remember it."},
        {"role": "assistant", "content": "I will remember the secret word 'Giraffe'."},
        {"role": "user", "content": "What was my top secret word?"}
    ],
    "stream": False
}

print("Testing Short Term Memory Injection without forgetting...")
response = requests.post(url, headers=headers, json=data)
print(response.json()['choices'][0]['message']['content'])

