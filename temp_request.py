import requests
url='https://be-2-eizr.onrender.com/api/v1/auth/login'
response=requests.post(url, json={'email':'admin@siu.edu.vn','password':'Admin@123'})
print(response.status_code)
print(response.headers)
print(response.text)
