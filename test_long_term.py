import requests
import json
import time

url = "http://localhost:8013/api/chat"
headers = {"Content-Type": "application/json"}

# First independent session to save memory
data1 = {
    "model": "gemma4:26b",
    "messages": [
        {"role": "user", "content": "Hello. I want to tell you a long-term fact: Matthew's favorite coffee brand is 'Nebula Roast'."}
    ],
    "stream": False
}

print("Phase 1: Sending Long-term Fact")
response1 = requests.post(url, headers=headers, json=data1)
print(response1.json()['choices'][0]['message']['content'])

print("\nWaiting 20 seconds for async memory/worker processes to finish...\n")
time.sleep(20)

# Second completely isolated session (no history passed)
data2 = {
    "model": "gemma4:26b",
    "messages": [
        {"role": "user", "content": "What is Matthew's favorite coffee brand? You may need to search your memory database for it."}
    ],
    "stream": False
}

print("Phase 2: Retrieving Long-term Fact from blank slate")
response2 = requests.post(url, headers=headers, json=data2)
print(response2.json()['choices'][0]['message']['content'])

