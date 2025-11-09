"""Generate a test RSA private key for integration tests."""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate test key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

# Save to file
with open("tests/fixtures/test_private_key.pem", "wb") as f:
    f.write(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

print("[OK] Test private key generated at tests/fixtures/test_private_key.pem")
