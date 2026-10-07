import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_otp_email(email, otp):
    """
    Sends a 6-digit OTP verification email to the user.
    Uses SMTP settings from environment variables.
    """
    sender_email = os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("MAIL_PASSWORD")
    smtp_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("MAIL_PORT", 587))

    if not sender_email or not sender_password:
        print("Error: MAIL_USERNAME or MAIL_PASSWORD not set in environment.")
        return False

    # Create the email content
    message = MIMEMultipart()
    message["From"] = f"Jaguar AI <{sender_email}>"
    message["To"] = email
    message["Subject"] = "Verify your Jaguar AI Account"

    body = f"""
    <html>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333;">
        <h2 style="color: #20e6d7;">Welcome to Jaguar AI</h2>
        <p>Thank you for registering. To complete your account setup, please use the following verification code:</p>
        <div style="font-size: 24px; font-weight: bold; color: #20e6d7; background: #101820; display: inline-block; padding: 10px 20px; border-radius: 5px; margin: 20px 0;">
          {otp}
        </div>
        <p>This code will expire in 10 minutes.</p>
        <p>If you did not request this email, please ignore it.</p>
        <br>
        <p>Stay Sharp,<br>Jaguar AI Team</p>
      </body>
    </html>
    """
    message.attach(MIMEText(body, "html"))

    try:
        # Connect to the SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send OTP email to {email}: {e}")
        return False
