import os
# import requests

# # The URL of your running FastAPI server
# url = "http://localhost:8003/generate"

# # The data structure matching your Pydantic model
# data = {
#     "system_prompt": "You are an encyclopedia. Answer the question.",
#     "query": "What is the capital of France?",
#     "max_new_tokens": 1000
# }

# # Send the request
# response = requests.post(url, json=data)

# # Check and print the result
# if response.status_code == 200:
#     print("AI Response:", response.json()["response"])
# else:
#     print(f"Error {response.status_code}: {response.text}")


import pandas as pd
from datetime import datetime

# 1. Define the exact columns from your schema
columns = [
    "company_email",
    "weblink",
    "role",
    "location",
    "source_file",
    "company_description",
    "timestamp",
    "status"
]

# 2. Create the data for the two rows
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

data = [
    {
        "company_email": "asadirfan939@gmail.com",
        "weblink": "https://openai.com",
        "role": "AI/ML Engineer",
        "location": "San Francisco, CA",
        "company_description": "AI research and deployment company.",
    },
    {
        "company_email": "u2022120@gmail.com",
        "weblink": "https://stripe.com",
        "role": "Software Engineer",
        "location": "Remote",
        "company_description": "Financial infrastructure platform for the internet.",
    }
]

# 3. Create the DataFrame and populate it with the data
df = pd.DataFrame(data, columns=columns)

# 4. Export to an Excel file (.xlsx)
output_path = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'AgenticControl/job_applications_template.xlsx'))
df.to_excel(output_path, index=False)

print(f"Success! {output_path} has been created with 2 rows of data.")