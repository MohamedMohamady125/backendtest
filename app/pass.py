from passlib.hash import bcrypt

password = "MmmM1234"
password_hash = bcrypt.hash(password)
print(password_hash)