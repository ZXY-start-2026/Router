import requests


URL = "https://inference.cluster.aimodelnetwork.cn/Intel/Qwen3.5-4B-int4-AutoRound/v1/completions"
BODY = {
    "prompt": "1+1=",
    "max_tokens": 1,
    "temperature": 0,
    "logprobs": 10,
    "logprobs_mode": "raw_logits"
}


def test_connect():
    resp = requests.post(URL, json=BODY)
    print(resp.json())
    resp.raise_for_status()


if __name__ == "__main__":
    test_connect()