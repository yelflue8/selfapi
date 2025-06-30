import base64
import mimetypes
import os
import random
import string
from email.message import EmailMessage

USA_FIRST_NAMES = ['alex', 'allen', 'michael', 'sarah', 'jessica', 'daniel', 'emily', 'joshua']
USA_LAST_NAMES = ['hill', 'raise', 'frank', 'smith', 'johnson', 'williams', 'brown', 'jones']

USA_STREETS = [
    "123 Maple St", "456 Oak Ave", "789 Pine Rd", "101 Elm Blvd", "202 Cedar Ln"
]
USA_CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix"
]
USA_ZIP_CODES = [
    "10001", "90001", "60601", "77001", "85001"
]

def random_us_name_file_ext(ext):
    first = random.choice(USA_FIRST_NAMES)
    last = random.choice(USA_LAST_NAMES)
    num = random.randint(10, 99)
    return f"{first}_{last}{num}.{ext}"

def random_price():
    return f"${random.uniform(310.99, 899.99):.2f}"

def random_address():
    street = random.choice(USA_STREETS)
    city = random.choice(USA_CITIES)
    zip_code = random.choice(USA_ZIP_CODES)
    return f"{street}, {city}, {zip_code}, United States"

def random_upper_letters(n=10):
    return ''.join(random.choices(string.ascii_uppercase, k=n))

def random_digits(n=10):
    return ''.join(random.choices(string.digits, k=n))

def replace_tags(text, email):
    price = random_price()
    address = random_address()
    random_letters = random_upper_letters()
    random_nums = random_digits()

    text = text.replace("#email", email)
    text = text.replace("#price", price)
    text = text.replace("#address", address)
    text = text.replace("#random", random_letters)
    text = text.replace("#number", random_nums)
    return text

def create_message_with_attachment(sender, to, subject, message_text, attachment_path=None, renamed_filename=None):
    message = EmailMessage()
    message['To'] = to
    message['From'] = sender
    message['Subject'] = subject

    # Detect if body is HTML or plain text by checking tags, you can adjust detection as needed
    if '<html>' in message_text.lower() or '<body>' in message_text.lower():
        message.set_content('This email requires an HTML-capable client.')
        message.add_alternative(message_text, subtype='html')
    else:
        message.set_content(message_text)

    if attachment_path and os.path.isfile(attachment_path):
        content_type, encoding = mimetypes.guess_type(attachment_path)
        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'

        main_type, sub_type = content_type.split('/', 1)

        with open(attachment_path, 'rb') as f:
            file_data = f.read()

        filename = renamed_filename if renamed_filename else os.path.basename(attachment_path)

        message.add_attachment(file_data, maintype=main_type, subtype=sub_type, filename=filename)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw_message}
