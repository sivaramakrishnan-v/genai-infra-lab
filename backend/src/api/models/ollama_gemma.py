import requests
import json

url = "http://localhost:11434/api/generate"

payload = {
    "model": "gemma3:270m",
    "prompt": "Explain embeddings in simple terms",
    "stream": False
}

response = requests.post(url, json=payload)
response.raise_for_status()

result = response.json()
print(result["response"])
