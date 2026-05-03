import requests
import re

session = requests.Session()
# 1. Fetch forgot-password
r1 = session.get('http://127.0.0.1:5000/forgot-password')
print("GET /forgot-password:", r1.status_code)

match = re.search(r'name="csrf_token" value="([^"]+)"', r1.text)
csrf_token = match.group(1) if match else ''

# 2. Post forgot-password
data = {'email': 'S-2024-001', 'csrf_token': csrf_token} # Wait, S-2024-001 is a student ID. In the template: placeholder="name@example.com", wait, is it email or USID?
# "Your OTP and Unique ID (e.g. S-2024-001) will be sent to this email." -> it's an email!
# In loginPY.py: cursor.execute("SELECT usid, email FROM Students WHERE email = %s", (email,))
# Let's assume an email exists or mock it? 
# If it fails to find email, it will redirect back to forgot-password, BUT it won't set session variables!
