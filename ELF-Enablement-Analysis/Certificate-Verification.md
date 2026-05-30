# Certificate Verification - Local vs z/OS

## Objective

Verify that the certificates used by c3270 locally match the certificates stored in z/OS RACF keyrings.

## Local Certificate Information

### Client Certificate (fultonm_cert.pem)
- **Subject**: C=US, O=Express Logon Client, CN=FULTONM
- **Issuer**: C=US, O=Express Logon Client, CN=FULTONM (self-signed)
- **Valid**: Mar 24 2026 - Jan 1 2028
- **SHA256 Fingerprint**: `48:47:24:71:17:B8:3E:23:27:83:75:3F:D9:CC:EF:EC:4E:BF:4B:D6:1C:3F:B4:18:DA:84:B0:8D:4D:0D:AC:CC`
- **Status**: â Valid, readable, matches private key

### Client Private Key (fultonm_key.pem)
- **Type**: RSA 2048-bit
- **Status**: â Valid, matches certificate

### Server CA Certificate (STD1_server.pem)
- **Subject**: O=z/OS, OU=TN3270 Server, CN=STD1
- **Issuer**: O=z/OS, OU=TN3270 Server, CN=STD1 (self-signed)
- **Valid**: Mar 26 2026 - Jan 1 2031
- **SHA256 Fingerprint**: `52:C4:92:C1:DB:79:CD:94:5A:B5:D0:06:4A:A9:A3:2E:53:B8:F6:3A:FA:1C:E5:A1:30:A5:1E:98:D7:F6:13:99`
- **Status**: â Valid, readable

## z/OS Certificate Verification Steps

### Step 1: Export Client Certificate from z/OS

```bash
# On z/OS, export the client certificate
racdcert export(label('FULTONM_CLIENT_CERT')) id(FULTONM) \
  dsn('FULTONM.CLIENT.CERT') format(certb64)

# Download to local system
# (Use download-dataset.sh or similar method)

# Convert to PEM and check fingerprint
openssl x509 -in fultonm_client_zos.pem -noout -fingerprint -sha256
```

**Expected Fingerprint**: `48:47:24:71:17:B8:3E:23:27:83:75:3F:D9:CC:EF:EC:4E:BF:4B:D6:1C:3F:B4:18:DA:84:B0:8D:4D:0D:AC:CC`

### Step 2: Export Server Certificate from z/OS

```bash
# On z/OS, export the server certificate
racdcert export(label('TN3270 Server')) id(SYSTEM) \
  dsn('SYSTEM.TN3270.CERT') format(certb64)

# Download to local system

# Convert to PEM and check fingerprint
openssl x509 -in tn3270_server_zos.pem -noout -fingerprint -sha256
```

**Expected Fingerprint**: `52:C4:92:C1:DB:79:CD:94:5A:B5:D0:06:4A:A9:A3:2E:53:B8:F6:3A:FA:1C:E5:A1:30:A5:1E:98:D7:F6:13:99`

### Step 3: Verify Certificate Details

```bash
# Compare subject and issuer
openssl x509 -in fultonm_client_zos.pem -noout -subject -issuer -dates
openssl x509 -in tn3270_server_zos.pem -noout -subject -issuer -dates
```

## Alternative: Use RACDCERT LIST

Instead of exporting, you can list certificate details on z/OS:

```bash
# List client certificate
racdcert list(label('FULTONM_CLIENT_CERT')) id(FULTONM)

# List server certificate
racdcert list(label('TN3270 Server')) id(SYSTEM)
```

Look for:
- Subject DN
- Issuer DN
- Serial number
- Validity dates
- Trust status

## OpenSSL s_client Test Results

When we tested with OpenSSL s_client, the server presented this certificate:

```
Server certificate
subject=O=z/OS, OU=TN3270 Server, CN=STD1
issuer=O=z/OS, OU=TN3270 Server, CN=STD1
```

This matches our local STD1_server.pem file â

The server also listed acceptable client certificate CA names:
```
Acceptable client certificate CA names:
- C=US, O=International Business Machines, OU=ZOSVSI, CN=SYSTEM_VS01TelnetCert
- C=US, O=International Business Machines, OU=ZOSVSI, CN=9.47.80.126_SELF_CACERT
- O=z/OS, OU=TN3270 Server, CN=STD1
- C=US, O=Express Logon Client, CN=FULTONM  â Our client cert CA
```

This confirms the server accepts our client certificate â

## Verification Checklist

- [ ] Local client cert fingerprint matches z/OS FULTONM_CLIENT_CERT
- [ ] Local server cert fingerprint matches z/OS TN3270 Server cert
- [ ] Client certificate is in FULTONM's TELNET_RING keyring
- [ ] Client certificate is marked as CERTAUTH in TELNET_RING
- [ ] Server certificate is in SYSTEM's TELNET_RING keyring
- [ ] Server certificate is marked as DEFAULT
- [ ] Server certificate has private key associated
- [ ] Certificate validity dates are current

## Expected Results

If certificates match:
- â OpenSSL s_client connects successfully (CONFIRMED)
- â c3270 fails with error 1030-01 (CURRENT ISSUE)

This confirms:
- Certificates are correct
- Server configuration is correct
- **Problem is specific to c3270's TLS implementation**

## Next Steps After Verification

Once we confirm certificates match, the issue is definitively in c3270's TLS handshake:

1. **Capture TLS handshake packets** (see TLS-Capture-Guide.md)
2. **Compare ClientHello messages** between OpenSSL and c3270
3. **Look for missing SNI** (Server Name Indication)
4. **Check TLS extensions** compatibility
5. **Examine c3270 source code** for TLS initialization

## Quick Verification Command

Run this on z/OS to get certificate info:

```bash
# Client cert
racdcert list(label('FULTONM_CLIENT_CERT')) id(FULTONM) | \
  grep -E "Subject|Issuer|Serial|Start Date|End Date"

# Server cert
racdcert list(label('TN3270 Server')) id(SYSTEM) | \
  grep -E "Subject|Issuer|Serial|Start Date|End Date"
```

Compare output with local certificate details above.