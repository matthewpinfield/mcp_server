# test_basic.py
from qwen_agent.agents import Assistant

llm_config = {
    'model': 'qwen3:8b',
    'model_server': 'http://localhost:11434/v1',
    'api_key': 'EMPTY'
}

bot = Assistant(llm=llm_config)
messages = [{"role": "user", "content": "Hello"}]

for response in bot.run(messages=messages):
    print(response)