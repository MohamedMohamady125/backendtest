from passlib.hash import bcrypt

password = "MIdo@2013"
password_hash = bcrypt.hash(password)
print(password_hash)