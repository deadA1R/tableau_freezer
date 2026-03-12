import datetime
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# 1. Генерируем приватный ключ
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2. Создаем структуру сертификата
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, u"127.0.0.1"),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.datetime.utcnow()
).not_valid_after(
    datetime.datetime.utcnow() + datetime.timedelta(days=365)
).add_extension(
    # Здесь мы указываем альтернативные имена, чтобы браузер не ругался
    x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName(u"localhost")
    ]),
    critical=False,
).sign(key, hashes.SHA256())

# 3. Сохраняем файлы в текущую папку
with open("key.pem", "wb") as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

with open("cert.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print("✅ Готово! Файлы key.pem и cert.pem созданы в C:\\tableau_freezer\\")