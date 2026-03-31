import requests
import uuid

url = "http://localhost:3000/api/run/cc4c0fff-01a9-4618-8473-64495cb35082?env=1&version=v1"
headers = {
    "Content-Type": "application/json",
    "x-api-key": "agk_jZRJ1LCnjGUzZL08RPKxMTIl3ohFcW64vcZ59YaQgmI"
}
# Use one session_id per conversation and reuse it for follow-up calls.
#session_id = str(uuid.uuid4())
session_id = "b58353da-54a8-4021-8e1e-8b2f6a865e56"  # For testing purposes, you can use a fixed session_id.
payload = {
    "input_value": "can you tell me my name ?",
    "session_id": session_id
}

response = requests.post(url, json=payload, headers=headers)
print("session_id:", response.headers.get("X-Session-Id", session_id))
print(response.json())


# import requests
# import uuid

# url = "http://localhost:3000/api/run/cc4c0fff-01a9-4618-8473-64495cb35082?env=1&version=v2"
# headers = {
#     "Content-Type": "application/json",
#     "x-api-key": "agk_nVOGtxVthCCBvLBS2MUZ471p0GxejoTPdoMkoF5vX3o"
# }
# # Use one session_id per conversation and reuse it for follow-up calls.
# session_id = str(uuid.uuid4())
# #session_id = "f1c22964-edfe-4a32-8296-251bf8ffe513"  # For testing purposes, you can use a fixed session_id.
# payload = {
#     "input_value": "Can you tell me two poimt about me  ?",
#     "session_id": session_id
# }

# response = requests.post(url, json=payload, headers=headers)
# print("session_id:", response.headers.get("X-Session-Id", session_id))
# print(response.json())

# import requests
# import uuid

# url = "http://localhost:3000/api/run/cc4c0fff-01a9-4618-8473-64495cb35082?env=1&version=v4"
# headers = {
#     "Content-Type": "application/json",
#     "x-api-key": "agk_Wb4n2iH12Fh87m37em8KgauBji1PblINHQl-YGreMNc"
# }
# # Use one session_id per conversation and reuse it for follow-up calls.
# session_id = str(uuid.uuid4())
# payload = {
#     "input_value": "What you remember about this user from previous sessions?",
#     "session_id": session_id
# }

# response = requests.post(url, json=payload, headers=headers)
# print("session_id:", response.headers.get("X-Session-Id", session_id))
# print(response.json())