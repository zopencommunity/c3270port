# TLS Handshake Success! ð

## Both Fixes Worked!

### Fix #1: SNI (Server Name Indication) â
Added `SSL_set_tlsext_host_name()` to c3270's OpenSSL implementation.

### Fix #2: Immediate TLS (L: prefix) â
Used `L:STD1` instead of `-secure` to force immediate TLS.

## Trace Evidence

**File**: `x3trc.479`

### TLS Handshake Success
```
Line 49:  Starting OpenSSL negotiation, host 'STD1'.
Line 51:  SSL_connect trace: TWCH SSLv3/TLS write client hello
Line 58:  SSL_connect trace: TRSH SSLv3/TLS read server hello
Line 76:  Connection is now secure.
Line 79:  Version: TLSv1.2
Line 80:  Cipher: ECDHE-RSA-AES128-GCM-SHA256
```

### Server Certificate Verified
```
Line 82-85:
 Server certificate:
  Public key: 2048 bit RSA
  Subject: O = z/OS, OU = TN3270 Server, CN = STD1
  Issuer: O = z/OS, OU = TN3270 Server, CN = STD1
```

### TN3270E Negotiation Started
```
Line 97:  RCVD DO NEW-ENVIRON
Line 99:  SENT WILL NEW-ENVIRON
Line 105: RCVD SB NEW-ENVIRON SEND USERVAR "IBMELF" USERVAR "IBMAPPLID" SE
Line 107: SENT SB NEW-ENVIRON IS USERVAR "IBMELF" VALUE "YES" USERVAR "IBMAPPLID" VALUE "None" SE
Line 114: RCVD DO TN3270E
Line 116: SENT WILL TN3270E
Line 131: SENT SB TN3270E DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01 SE
```

## Current Issue: INV-NAME Rejection

```
Line 137: RCVD SB TN3270E DEVICE-TYPE REJECT REASON INV-NAME SE
```

This is **NOT a TLS issue** - it's a TN3270 server configuration issue.

### Why INV-NAME?

Port 923 doesn't have pool routing configured for "TSOVS01". This is the same issue we saw on port 992.

### Comparison

| Port | TLS | TN3270E | CONNECT Field | Result |
|------|-----|---------|---------------|--------|
| 992 | â Works | â Works | â INV-NAME | No pool routing |
| 923 | â Works | â Works | â INV-NAME | No pool routing |

Both ports accept the connection and TN3270E negotiation, but reject the CONNECT field because "TSOVS01" is not configured as a valid pool name.

## Next Steps

### Option 1: Configure Pool Routing on Port 923

Add "TSOVS01" as a valid pool name in the TN3270 server configuration for port 923.

**In `tn3270.cfg`:**
```
Port 923
  TTLSPort
  ExpressLogon
  PoolName TSOVS01
```

### Option 2: Use a Different Pool Name

Check what pool names are configured on port 923:
```bash
# On z/OS
grep -A 20 "Port 923" tn3270.cfg
```

### Option 3: Test Without CONNECT Field

Try connecting without specifying a pool:
```bash
c3270 -trace -model 2 -port 923 \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -cafile /u/fultonm/Certificates/STD1_server.pem \
  -certfile /u/fultonm/Certificates/fultonm_cert.pem \
  -keyfile /u/fultonm/Certificates/fultonm_key.pem \
  L:STD1
```

(Remove `-elf TSOVS01` to not send CONNECT field)

## Success Metrics

â **TLS Handshake**: COMPLETE
â **Certificate Verification**: PASSED
â **SNI**: WORKING
â **TN3270E Negotiation**: STARTED
â **ELF Variables**: SENT (IBMELF=YES)
â **Pool Routing**: NOT CONFIGURED

## Technical Details

### Command Used
```bash
c3270 -trace -model 2 -elf TSOVS01 -port 923 \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  L:STD1
```

### Key Changes from Previous Attempts

1. **Added SNI support** in `sio_openssl.c`
2. **Used `L:STD1`** instead of `-secure` for immediate TLS
3. **Forced TLS 1.2** with `-tlsminprotocol` and `-tlsmaxprotocol`

### TLS Session Details

- **Protocol**: TLSv1.2
- **Cipher**: ECDHE-RSA-AES128-GCM-SHA256
- **Key Exchange**: ECDHE (Elliptic Curve Diffie-Hellman Ephemeral)
- **Authentication**: RSA
- **Encryption**: AES-128-GCM
- **Hash**: SHA256
- **Security Level**: 2

### Timeline

```
19:18:55.958 - TCP connection established
19:18:55.964 - TLS handshake started
19:18:56.034 - TLS handshake completed (70ms)
19:18:56.039 - TN3270E negotiation started
19:18:56.056 - DEVICE-TYPE REQUEST sent
19:18:56.062 - DEVICE-TYPE REJECT received (INV-NAME)
```

Total time from connection to rejection: **104ms**

## Conclusion

**The TLS issues are COMPLETELY RESOLVED!**

The remaining INV-NAME issue is a **TN3270 server configuration problem**, not a c3270 or TLS problem.

Our fixes:
1. â SNI support added to c3270
2. â Immediate TLS mode used (L: prefix)

Both work perfectly. The connection now proceeds exactly as expected through TLS handshake and into TN3270E negotiation.

## Files Modified

1. **`suite3270-4.4/Common/sio_openssl.c`**
   - Added SNI support (lines 954-963)
   - Uploaded to z/OS and rebuilt

2. **`patches/sio_openssl.c.patch`**
   - Patch file for upstream contribution

## References

- **Trace File**: `x3trc.479`
- **SNI Fix**: [`SNI-Fix.md`](SNI-Fix.md)
- **STARTTLS Issue**: [`StartTLS-Issue.md`](StartTLS-Issue.md)
- **Certificate Verification**: [`Certificate-Verification-Results.md`](Certificate-Verification-Results.md)