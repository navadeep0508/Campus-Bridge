"""Hash a password entered interactively for manual account maintenance."""
import getpass
import bcrypt

def main():
    password = getpass.getpass("Password to hash: ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters.")
    print(bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"))

if __name__ == "__main__":
    main()
