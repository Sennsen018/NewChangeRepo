import requests
import re
from bs4 import BeautifulSoup

session = requests.Session()
r1 = session.get('http://127.0.0.1:5000/forgot-password')
print("GET /forgot-password:", r1.status_code)

match = re.search(r'name="csrf_token" value="([^"]+)"', r1.text)
csrf_token = match.group(1) if match else ''

data = {'email': 'test@example.com', 'csrf_token': csrf_token}
r2 = session.post('http://127.0.0.1:5000/forgot-password', data=data)
print("POST /forgot-password:", r2.status_code)
print("URL after POST:", r2.url)

r3 = session.get('http://127.0.0.1:5000/verify-otp')
print("GET /verify-otp:", r3.status_code)
print("Rendered verify-otp snippet:", r3.text[:200])

