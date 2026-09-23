# I want to understand where intelligence is useful in a real business workflow


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.user.routes import register

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def root():
    return "hello world"


app.add_api_route(path="/register", methods=["POST"], endpoint=register)
