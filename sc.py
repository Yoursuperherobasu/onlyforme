import requests

url = "http://localhost:3000/api/run/53eccd14-6818-40d7-a702-fd8551c6f6cf?env=1&version=v4"
headers = {
    "Content-Type": "application/json",
    "x-api-key": "agk_fsxPf8lflkpqS6xjLi-Yqem55Jmdu98ul8NppTIWcyY"
}
payload = {
    "input_value": "Hello!"
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())