import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_email(name: str, email: str, message: str):
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_USER or EMAIL_PASSWORD not set in .env")

    msg = EmailMessage()
    msg["Subject"] = f"MediDevice Support Query from {name}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Reply-To"] = email
    msg.set_content(
        f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
