import common
import json
import state

from openai import OpenAI

_openai_client = None

_logger = common.get_logger("GPT")

_prompt_fix_json = ""

with open(f"prompts/fix_json.txt", "r") as file:
    _prompt_fix_json = file.read()

def init(api_key: str) -> None:
    global _openai_client
    _openai_client = OpenAI(api_key=api_key)

def _make_prompt_fix_json(json_text: str, json_error: str) -> str:
    prompt = _prompt_fix_json
    prompt = prompt.replace("@json@", json_text)
    prompt = prompt.replace("@error@", json_error)

    return prompt

def request(system: str, prompt: str, images: list[str] = [], temperature = 0.1,
            model = "gpt-4-turbo-preview", json: bool = False) -> str:
    image_urls = []

    for image in images:
        image_urls.append({"type": "image_url", "image_url": { "url": image }})

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
        ]}
    ]

    messages[1]["content"].extend(image_urls)

    if json:
        completion = _openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=4096
        )
    else:
        completion = _openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=4096
        )

    return completion.choices[0].message.content

def _get_response_json(text: str, allow_fix = True) -> dict:
    json_data = {}

    try:
        json_data = json.loads(text)
    except Exception as e:
        _logger.error(f"JSON parse error: {e} (Can fix: {allow_fix}))")

        if allow_fix:
            # Attempt to fix JSON
            prompt = _make_prompt_fix_json(text, str(e))
            response_text = request("", prompt=prompt, images=[])
            json_data = _get_response_json(response_text, allow_fix=False)

            if json_data == {}:
                _logger.error("Failed to fix JSON")

    return json_data

def request_json(system: str, prompt: str, model = "gpt-3.5-turbo") -> dict:
    response_text = request(system, prompt, [], 0.1, model=model, json=True)
    response_json = _get_response_json(response_text)

    return response_json
