from html import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth.controllers.verify import verify
from app.auth.controllers.resend_verification import resend_verification
from app.auth.schemas.verify import VerifyRequest
from app.auth.schemas.resend_verification import ResendVerificationRequest
from app.database import get_db

router = APIRouter()


@router.post("/api/v1/verify")
def verify_user(data: VerifyRequest, session: Session = Depends(get_db)):
    return verify(token=data.token, session=session)


@router.get("/api/v1/verify", response_class=HTMLResponse)
def verify_confirmation_page(token: str):
    # Loading the link is read-only; email link scanners must not verify users.
    safe_token = escape(token, quote=True)
    return HTMLResponse(
        "<!doctype html><html><body>"
        "<h1>Verify your email</h1>"
        "<p>Confirm below to activate your account.</p>"
        f'<button id="confirm" data-token="{safe_token}">Confirm email</button>'
        "<p id=\"result\"></p>"
        "<script>"
        "document.getElementById('confirm').addEventListener('click', async event => {"
        "const button = event.currentTarget; button.disabled = true;"
        "const response = await fetch('/api/v1/verify', {method:'POST',"
        "headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({token:button.dataset.token})});"
        "const result = await response.json();"
        "document.getElementById('result').textContent = result.message;"
        "});"
        "</script></body></html>"
    )


@router.post("/api/v1/verify/resend")
def resend_verification_email(
    data: ResendVerificationRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    return resend_verification(data=data, request=request, session=session)
