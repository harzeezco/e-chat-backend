from app.auth.services.email_send import send_email


def create_verify_email(email: str, token: str):
    verification_url = f"http://localhost:8000/api/v1/verify?token={token}"

    send_email(
        to=email,
        subject="Verify your account",
        body=(
            "Welcome!\n\n"
            "Please verify your account by clicking the link below:\n\n"
            f"{verification_url}\n\n"
            "This link will expire in 10 minutes."
        )
    )

