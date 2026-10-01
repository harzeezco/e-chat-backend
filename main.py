# I want to understand where intelligence is useful in a real business workflow


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.auth.routes.register import router as register_router
from app.auth.routes.verify import router as verify_router
from app.auth.routes.login import router as login_router

app = FastAPI()


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 500,
            "message": "An unexpected error occurred. Please try again later.",
            "data": [],
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/health")
def root():
    return "hello world"


app.include_router(register_router)
app.include_router(login_router)
app.include_router(verify_router)
