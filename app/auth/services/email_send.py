import smtplib
from email.message import EmailMessage


def send_email(to: str, subject: str, body: str):
    message = EmailMessage()
    message["From"] = "wakil@gmail.com"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP("mailpit", 1025, timeout=20) as smtp:
        smtp.send_message(message)
