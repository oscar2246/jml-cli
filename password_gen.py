import secrets
import string
from random import SystemRandom

letter_count = 3
int_count = 4
special_char_count = 2

def generate():
    password_upper = ''
    for i in range(letter_count):
        upper = secrets.choice(string.ascii_uppercase)
        password_upper += upper

    password_lower = ''
    for i in range(letter_count):
        lower = secrets.choice(string.ascii_lowercase)
        password_lower += lower

    password_int = ''
    for i in range(int_count):
        integer = secrets.choice(string.digits)
        password_int += integer

    password_special_char = ''
    symbols = '!#$%*+-=?@'
    for i in range(special_char_count):
        special_char = secrets.choice(symbols)
        password_special_char += special_char

    chars = list(password_upper + password_lower + password_int + password_special_char)
    SystemRandom().shuffle(chars)
    otp_password = ''.join(chars)
    return otp_password

if __name__ == "__main__":
    print(generate())
