# Dolt Database TLS Configuration Guide

**Environment:**
- Dolt 1.82.4
- OpenSSL 3.6.1
- MySQL Client 8.4.8 (Homebrew, macOS arm64)
- macOS 15.2
- Database Hosted on Mac M1

---

## Architecture: Centralized Certificate Storage

Store TLS certs centrally — not per-database. One cert covers all dolt databases on the machine. Each database's `config.yaml` simply references the central cert path by absolute path.

In this example we will put the central dolt cert repository in our home directory (~) in a hidden directory `.dolt`.

**Directory layout:**

```
~/.dolt/
├── certs/
│   ├── ca-key.pem          # CA private key (keep secret, never share)
│   ├── ca-cert.pem         # CA certificate (distribute to clients)
│   ├── ca-cert.srl         # CA serial file (auto-generated)
│   ├── server-key.pem      # Server private key
│   ├── server-cert.pem     # Server certificate (signed by CA)
│   ├── server-req.pem      # CSR (intermediate, can delete after signing)
│   └── server-san.cnf      # SAN config file (keep for future regeneration)
└── dolt/                   # This top level directory holds all my dolt databases
    └── my_db/
        └── .dolt/
            └── config.yaml  # References certs by absolute path
    └── launches/
        └── .dolt/
            └── config.yaml  # References certs by absolute path
```

---

## Step 1: Set Up Hostnames in /etc/hosts

```
127.0.0.1       localhost mac-minim1.local doltserver.local
255.255.255.255 broadcasthost
::1             localhost
10.1.10.21      mac-minim1.local
```

Edit with:
```bash
sudo nano /etc/hosts
```

> Using hostnames is strongly recommended over bare IPs. Modern TLS (OpenSSL 3.x, MySQL 8.x) validates Subject Alternative Names (SANs). Both the IP and hostname are included in the cert SANs to cover all access patterns.

---

## Step 2: Create Certificate Directory

```bash
mkdir -p ~/.dolt/certs
chmod 700 ~/.dolt/certs
cd ~/.dolt/certs
```

---

## Step 3: Generate the CA (Certificate Authority)

```bash
# Generate CA private key
openssl genrsa -out ca-key.pem 4096

# Generate CA certificate (self-signed, valid 10 years)
openssl req -new -x509 \
  -days 3650 \
  -key ca-key.pem \
  -out ca-cert.pem \
  -subj "/C=US/ST=Lab/L=Lab/O=LabCA/CN=LabRootCA"

chmod 600 ca-key.pem
chmod 644 ca-cert.pem
```

---

## Step 4: Create the SAN Config File

```bash
cat > ~/.dolt/certs/server-san.cnf << 'EOF'
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = req_ext

[dn]
C  = US
ST = Lab
L  = Lab
O  = LabServer
CN = mac-minim1.local

[req_ext]
subjectAltName = @alt_names

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = mac-minim1.local
DNS.2 = doltserver.local
DNS.3 = localhost
IP.1  = 127.0.0.1
IP.2  = 10.1.10.21
EOF
```

> Do **not** include `0.0.0.0` in the SANs — that is a bind address (listen on all interfaces), not an address a client connects to.

---

## Step 5: Generate the Server Certificate

```bash
cd ~/.dolt/certs

# Generate server private key
openssl genrsa -out server-key.pem 2048

# Generate Certificate Signing Request (CSR)
openssl req -new \
  -key server-key.pem \
  -out server-req.pem \
  -config server-san.cnf

# Sign the server cert with your CA (valid 3 years)
openssl x509 -req \
  -days 1095 \
  -in server-req.pem \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out server-cert.pem \
  -extensions req_ext \
  -extfile server-san.cnf

chmod 600 server-key.pem
chmod 644 server-cert.pem
```

---

## Step 6: Verify the Certificate

```bash
# Verify cert was signed by your CA
openssl verify -CAfile ~/.dolt/certs/ca-cert.pem ~/.dolt/certs/server-cert.pem
# Expected: server-cert.pem: OK

# Verify SANs are present (critical — must not be blank)
openssl x509 -in ~/.dolt/certs/server-cert.pem -noout -text | grep -A 6 "Subject Alternative Name"
# Expected output:
# X509v3 Subject Alternative Name:
#     DNS:mac-minim1.local, DNS:doltserver.local, DNS:localhost, IP Address:127.0.0.1, IP Address:10.1.10.21

# Verify key and cert match (hashes must be identical)
openssl x509 -noout -modulus -in ~/.dolt/certs/server-cert.pem | openssl md5
openssl rsa  -noout -modulus -in ~/.dolt/certs/server-key.pem  | openssl md5
```

---

## Step 7: Configure the Dolt Database

File location: `my_db/.dolt/config.yaml`

```yaml
log_level: info

behavior:
  read_only: false
  autocommit: true

user:
  name: root

listener:
  host: 0.0.0.0
  port: 3306
  tls_key:  /Users/claudia/.dolt/certs/server-key.pem
  tls_cert: /Users/claudia/.dolt/certs/server-cert.pem
  require_secure_transport: true

performance:
  query_parallelism: 0
```

> `host: 0.0.0.0` means listen on all network interfaces. Clients connect via a real IP or hostname — never `0.0.0.0` directly.
>
> `require_secure_transport: true` rejects all plaintext connections. Set to `false` temporarily during initial testing if needed.

---

## Step 8: Start the Server

```bash
cd ~/path/to/my_db
dolt sql-server --config .dolt/config.yaml
```

---

## Step 9: Verify TLS is Working

### From the command line (full cert chain verification):
```bash
openssl s_client -connect 127.0.0.1:3306 -starttls mysql \
  -CAfile /Users/claudia/.dolt/certs/ca-cert.pem | grep -E "Verify|Cipher|Protocol"
```
Expected:
```
New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256
Verify return code: 0 (ok)
```

### Verify plaintext is blocked:
```bash
mysql -h 127.0.0.1 -P 3306 -u admin -p --ssl-mode=DISABLED
# Expected: ERROR 1105 - server does not allow insecure connections
```

### Connect with TLS and verify:
```bash
mysql -h 127.0.0.1 -P 3306 -u admin -p \
  --ssl-ca /Users/claudia/.dolt/certs/ca-cert.pem \
  --ssl-mode=VERIFY_CA
```

### Inside the mysql prompt — best verification command:
```sql
status
```
Look for:
```
SSL: Cipher in use is TLS_AES_128_GCM_SHA256
```

> **Note:** `SHOW STATUS LIKE 'Ssl_cipher'` returns empty due to a MySQL 8.4 client / Dolt 8.0.33 reporting quirk. Use `status` instead — it correctly shows the cipher.

Other useful status queries:
```sql
SHOW STATUS LIKE 'Ssl_cipher';
SHOW STATUS LIKE 'Ssl_version';
SHOW STATUS LIKE 'Ssl_%';
```

---

## Multiple Databases

Each additional database gets its own `config.yaml` pointing to the **same cert files** but on a **different port**:

```yaml
listener:
  host: 0.0.0.0
  port: 3307
  tls_key:  /Users/claudia/.dolt/certs/server-key.pem
  tls_cert: /Users/claudia/.dolt/certs/server-cert.pem
  require_secure_transport: true
```

---

## Distributing Certs to Remote Clients

The only file clients need is `ca-cert.pem`. **Never share `ca-key.pem` or `server-key.pem`.**

Copy to remote client:
```bash
scp ~/.dolt/certs/ca-cert.pem user@remotemachine:~/
```

Connect from remote client:
```bash
mysql -h mac-minim1.local -P 3306 -u admin -p \
  --ssl-ca ~/ca-cert.pem \
  --ssl-mode=VERIFY_CA
```

To trust the CA system-wide on macOS (optional):
```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain ~/.dolt/certs/ca-cert.pem
```

---

## User Management

Connect as root to manage users:
```bash
mysql -h 127.0.0.1 -P 3306 -u root --ssl-mode=REQUIRED
```

List all users:
```sql
SELECT user, host FROM mysql.user;

-- With more detail:
SELECT user, host, plugin, authentication_string FROM mysql.user;
```

> Regular users (e.g. `admin`) do not have access to `mysql.user` — you must connect as `root`.

---

## File Permissions Summary

| File | Permission | Who needs it |
|---|---|---|
| `ca-key.pem` | `600` | Only the machine that signs certs |
| `ca-cert.pem` | `644` | Server + all clients |
| `server-key.pem` | `600` | Dolt server process only |
| `server-cert.pem` | `644` | Dolt server process |
| `server-req.pem` | can delete | Intermediate artifact only |
| `server-san.cnf` | `644` | Keep — needed to regenerate cert |

---

## Cert Renewal

When the server cert expires (3 years), regenerate using the same CA — no need to redistribute `ca-cert.pem` to clients:

```bash
cd ~/.dolt/certs

openssl req -new \
  -key server-key.pem \
  -out server-req.pem \
  -config server-san.cnf

openssl x509 -req \
  -days 1095 \
  -in server-req.pem \
  -CA ca-cert.pem \
  -CAkey ca-key.pem \
  -CAcreateserial \
  -out server-cert.pem \
  -extensions req_ext \
  -extfile server-san.cnf
```

Then restart the dolt server.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Ssl_cipher` empty in `SHOW STATUS` | MySQL 8.4 client reporting bug | Use `status` command instead |
| `server does not allow insecure connections` | `require_secure_transport: true` working correctly | Add `--ssl-mode=REQUIRED` or `VERIFY_CA` to client |
| `certificate verify failed` | Client missing `ca-cert.pem` | Pass `--ssl-ca` pointing to `ca-cert.pem` |
| SAN blank in cert | `-extensions req_ext -extfile` missing from sign command | Regenerate cert with both flags |
| Works locally, fails remotely | LAN IP missing from SANs | Add IP to `server-san.cnf` and regenerate cert |
| `Access denied to database 'mysql'` | Connected as non-root user | Reconnect as root to query `mysql.user` |
| `syntax error near '$'` in server log | MySQL 8.4 client init query incompatibility | Harmless noise — connection still works |
