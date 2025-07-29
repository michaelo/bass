import smtplib

from email.message import EmailMessage
from email.headerregistry import Address

def send_email(sender: str, recipients: str, subject: str, body: str):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = Address(username=sender)
    msg['To'] = [Address(username=recp) for recp in recipients.split(",")]
    msg.set_content(body) # plain
    msg.add_alternative(body, subtype="html") # html

    with smtplib.SMTP('localhost') as smtp:
        smtp.send_message(msg)


# if __name__ == "__main__":
#     send_email("bass@michaelodden.com", "Michael Odden <me@michaelodden.com>,Other Odden <me+bass@michaelodden.com>", "bass test: ${myvar}", """<h1>heisann!</h1><p><a href="#">link ${myvar}</a></p>""")