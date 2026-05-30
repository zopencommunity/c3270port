# TLS Handshake Deep Dive - Port 923 Issue

## Latest Test Results

### Test with TLS 1.2 Forced (18:52:41)

**Command**:
```bash
c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1
```

**Result**: â STILL FAILED with error 1030-01

**Server Log**:
```
18.52.41 STC00036  EZZ6034I TN3270 CONN 00001B30 LU **N/A**  ACCEPTED     923
   541               IP..PORT: ::FFFF:9.47.80.126..2023
18.52.49 STC00036  EZZ6035I TN3270 DEBUG CONN   DETAIL
   544               IP..PORT: ::FFFF:9.47.80.126..2023
   544               CONN: 00001B30  LU:          MOD: EZBTTXPL
   544               RCODE: 1030-01  TTLS Ioctl failed for query or init HS.
   544               PARM1: FFFFFFFF PARM2: 00000464 PARM3: 77B77221
18.52.49 STC00036  EZZ6034I TN3270 CONN 00001B30 LU **N/A**  CONN DROP  ERR 1030  
   545               IP..PORT: ::FFFF:9.47.80.126..2023                         EZBTTXPL
```

**Client Trace** (x3trc.16778499):
```
Line 41: Connected to STD1, port 923.
Line 42: cstate [not-connected] -> [telnet-pending] (net_connected_complete)
Lines 52-77: Waiting in scheduler loop, no data received
```

**Analysis**: 
- TCP connection succeeds
- TLS handshake never completes
- No data exchanged
- Connection hangs until timeout

### PCOMM Success (18:53:48) - For Comparison

**Server Log**:
```
18.53.48 STC00036  EZZ6034I TN3270 CONN 00001B3C LU **N/A**  ACCEPTED     923
   554               IP..PORT: ::FFFF:172.22.11.3..61849
18.53.48 STC00036  EZZ6034I TN3270 CONN 00001B3C LU TCP00008 NEGOTIATED TN3270E
   662               IP..PORT: ::FFFF:172.22.11.3..61849
18.53.48 STC00036  EZZ6034I TN3270 CONN 00001B3C LU TCP00008 IN SESSION A06TSO01
   664               IP..PORT: ::FFFF:172.22.11.3..61849
```

**Analysis**:
- â Connection accepted
- â TN3270E negotiated
- â Session established
- â No error 1030-01

## Key Finding: TLS Version is NOT the Problem

**Evidence**:
1. Forcing TLS 1.2 did NOT fix the issue
2. Same error 1030-01 persists
3. PCOMM works (likely also using TLS 1.2)
4. Error occurs during "query or init HS" (handshake initialization)

## Error 1030-01 Deep Analysis

### Error Details

```
RCODE: 1030-01  TTLS Ioctl failed for query or init HS.
PARM1: FFFFFFFF
PARM2: 00000464  (1124 decimal)
PARM3: 77B77221
```

### PARM2 Analysis

**Value**: 0x00000464 = 1124 decimal

This is likely an errno value. Common z/OS errno 1124 meanings:
- Certificate validation failure
- Client certificate not presented correctly
- Certificate chain incomplete
- Certificate format issue

### Module: EZBTTXPL

**EZBTTXPL** = AT-TLS processing module

This module handles:
- TLS handshake initialization
- Certificate validation
- Protocol negotiation
- Cipher suite selection

## Hypothesis: Certificate Issue

### Theory

The problem is NOT TLS version, but rather:
1. **Client certificate format** - PEM format may not be compatible
2. **Certificate chain** - Missing intermediate certificates
3. **Certificate label** - Server expects specific certificate label
4. **Certificate presentation timing** - c3270 presents cert at wrong time

### Evidence Supporting Certificate Theory

1. **Error occurs at handshake init** - Before protocol negotiation
2. **PCOMM works** - Uses different certificate or presentation method
3. **Port 992 works** - Different AT-TLS policy, less strict requirements
4. **Error 1030-01** - Specifically related to TLS initialization failure

### AT-TLS Certificate Requirements (Port 923)

From pagttls.conf:
```
TTLSEnvironmentAction EnvironmentActionTN3270
{
  HandshakeRole ServerWithClientAuth    â Requires client cert
  TTLSKeyringParms
  {
    Keyring SYSTEM/TELNET_RING
  }
  TTLSEnvironmentAdvancedParms
  {
    CertificateLabel TN3270 Server      â Specific cert label required
    ClientAuthType Required             â Client cert REQUIRED
  }
}
```

## Recommended Next Steps

### 1. Check Server Certificate Label

```bash
# On z/OS
RACDCERT LIST(LABEL('TN3270 Server')) ID(SYSTEM)
RACDCERT LISTRING(TELNET_RING) ID(SYSTEM)
```

**Expected**: Certificate labeled "TN3270 Server" should exist

**If missing**: This is the problem - AT-TLS cannot find server certificate

### 2. Check Client Certificate Format

```bash
# Verify certificate format
openssl x509 -in ${CERT_ROOT}/fultonm_cert.pem -text -noout

# Check if certificate is valid
openssl verify -CAfile ${CERT_ROOT}/STD1_server.pem ${CERT_ROOT}/fultonm_cert.pem
```

### 3. Test with OpenSSL s_client

```bash
# Test TLS handshake with OpenSSL
openssl s_client -connect std1:923 -tls1_2 \
  -cert ${CERT_ROOT}/fultonm_cert.pem \
  -key ${CERT_ROOT}/fultonm_key.pem \
  -CAfile ${CERT_ROOT}/STD1_server.pem \
  -showcerts -debug -state

# Look for:
# - Handshake completion
# - Certificate exchange
# - Any errors
```

### 4. Check AT-TLS Trace Logs

With Trace 255 enabled on port 923:

```bash
# On z/OS
D TCPIP,,TTLS,CONN,DETAIL

# Look for:
# - Certificate validation errors
# - Handshake failures
# - Specific error messages
```

### 5. Compare c3270 vs PCOMM Certificates

**Question**: Does PCOMM use the same certificates as c3270?

**Test**: Try c3270 with PCOMM's certificates (if different)

### 6. Simplify AT-TLS Configuration (Temporary)

To isolate the issue, temporarily modify port 923 AT-TLS config:

```
# In pagttls.conf, comment out:
# CertificateLabel TN3270 Server
# ClientAuthType Required

# Change to:
ClientAuthType PassThru  # Don't require client cert
```

**Then restart TCPIP** and test c3270 again.

If this works, the problem is definitely certificate-related.

## Alternative Theories

### Theory 2: Cipher Suite Mismatch

**Less likely** because:
- Port 923 allows 4 common cipher suites
- c3270 (OpenSSL) should support these
- Would expect different error code

**Test**:
```bash
# Check c3270's cipher suites
openssl ciphers -v | grep -E 'ECDHE-RSA-AES.*GCM|AES.*GCM'
```

### Theory 3: SNI (Server Name Indication) Issue

**Less likely** because:
- c3270 connects to "STD1" hostname
- Should send correct SNI
- Would expect different error

**Test**: Check if c3270 sends SNI in ClientHello

### Theory 4: Certificate Chain Issue

**Possible** if:
- Client certificate requires intermediate CA
- c3270 not sending full chain
- Server cannot validate client cert

**Test**:
```bash
# Check certificate chain
openssl s_client -connect std1:923 -showcerts \
  -cert ${CERT_ROOT}/fultonm_cert.pem \
  -key ${CERT_ROOT}/fultonm_key.pem
```

## Comparison: Port 992 vs Port 923

| Aspect | Port 992 (Works) | Port 923 (Fails) |
|--------|------------------|------------------|
| TLS Type | Regular TLS | AT-TLS |
| Certificate Label | None | "TN3270 Server" required |
| Client Auth | ServerWithClientAuth | ServerWithClientAuth + Required |
| User Instance | 0 | 1 |
| Trace Level | 1 | 255 |
| Result | â TLS succeeds | â Error 1030-01 |

**Key Difference**: Port 923 has stricter certificate requirements

## Conclusion

**TLS version is NOT the problem**. The issue is most likely:

1. **Server certificate label missing** ("TN3270 Server" not in SYSTEM/TELNET_RING)
2. **Client certificate format/chain issue**
3. **AT-TLS policy too strict for c3270's certificate presentation**

**Next Action**: Check if "TN3270 Server" certificate exists in SYSTEM/TELNET_RING keyring.

## References

- **Server Logs**: TN3270 job STC00036 JESMSGLG
- **Client Trace**: /tmp/x3trc.16778499
- **AT-TLS Policy**: pagttls.conf lines 588-634
- **Error Code**: IBM z/OS Communications Server IP Diagnosis Guide (Error 1030-01)