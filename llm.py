import time

def llmCall(message):
    # message is an array with 0th value being system instructions and 1st value being user input.
    import requests
    import json
    url = "https://api.together.xyz/v1/chat/completions"

    payload = {
        "model": "meta-llama/Llama-2-70b-chat-hf",
        "max_tokens": 512,
        "stop": ["</s>", "[/INST]"],
        "temperature": 0.1,
        "top_p": 0.1,
        "top_k": 50,
        "repetition_penalty": 1,
        "n": 1,
        "messages": [
            {
                "role": "system",
                "content": message[0]
            },
            {
                "role": "user",
                "content": message[1]
            }
        ]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": "Bearer <key>"
    }
    time.sleep(0.5)
    response = requests.post(url, json=payload, headers=headers)
    if "choices" in json.loads(response.text):
        return json.loads(response.text)["choices"][0]["message"]["content"]
    return None
