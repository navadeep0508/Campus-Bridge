import bcrypt

# Password to hash
password = "sunny@2005"

# Generate a salt
salt = bcrypt.gensalt()

# Hash the password
hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

# Print the hashed password
print(hashed_password.decode('utf-8'))