from fastapi import Request

def access_control(req: Request):
    cookie = req.cookies
    print(cookie)
