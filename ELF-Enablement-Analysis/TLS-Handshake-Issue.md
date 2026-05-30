# TLS Handshake Issue on Port 923 (ELF-Enabled)

## Problem Summary

c3270 connections to port 923 (ELF-enabled with AT-TLS) fail during TLS handshake initialization, while PCOMM connections succeed. The connection is accepted but drops immediately with error 1030-01.

## Server Log Evidence

### Failed c3270 Connection (9.47.80.126:2005)
```
18.29.01 STC00036  EZZ6034I TN3270 CONN 00001ADE LU **N/A**  ACCEPTED     923
   420               IP..PORT: ::FFFF:9.47.80.126..2005
18.29.13 STC00036  EZZ6035I TN3270 DEBUG CONN   DETAIL
   422               IP..PORT: ::FFFF:9.47.80.126..2005
   422               CONN: 00001ADE  LU:          MOD: EZBTTXPL
   422               RCODE: 1030-01  TTLS Ioctl failed for query or init HS.
   422               PARM1: FFFFFFFF PARM2: 00000464 PARM3: 77B77221
18.29.13 STC00036  EZZ6034I TN3270 CONN 00001ADE LU **N/A**  CONN DROP  ERR 1030
   424               IP..PORT: ::FFFF:9.47.80.126..2005                         EZBTTXPL
```

**Key Error**: `RCODE: 1030-01  TTLS Ioctl failed for query or init HS.`

### Successful PCOMM Connection (172.22.11.3:63451)
```
17.59.24 STC00036  EZZ6034I TN3270 CONN 00001391 LU **N/A**  ACCEPTED     923
   308               IP..PORT: ::FFFF:172.22.11.3..63451
17.59.25 STC00036  EZZ6034I TN3270 CONN 00001391 LU TCP00006 NEGOTIATED TN3270E
   416               IP..PORT: ::FFFF:172.22.11.3..63451
17.59.25 STC00036  EZZ6034I TN3270 CONN 00001391 LU TCP00006 IN SESSION A06TSO01
   418               IP..PORT: ::FFFF:172.22.11.3..63451
```

**Success**: Connection proceeds through TN3270E negotiation to session establishment.

## Error Analysis

### Error Code 1030-01
- **Module**: EZBTTXPL (AT-TLS processing module)
- **Meaning**: AT-TLS ioctl() call failed during TLS handshake initialization
- **Impact**: Connection dropped before any TLS negotiation occurs

### Comparison

| Aspect | c3270 (FAILS) | PCOMM (WORKS) |
|--------|---------------|---------------|
| TCP Connection | â Accepted | â Accepted |
| TLS Handshake | â Fails at init | â Succeeds |
| TN3270E Negotiation | â Never reached | â Succeeds |
| Session Establishment | â Never reached | â Succeeds |
| Error | 1030-01 TTLS Ioctl | None |

## Root Cause Hypotheses

### 1. TLS Protocol Version Mismatch (Most Likely)
- **Hypothesis**: c3270 requests TLS 1.3, but AT-TLS policy only allows TLS 1.2
- **Evidence**: AT-TLS on z/OS may have strict protocol version requirements
- **Test**: Check c3270's TLS version negotiation vs PCOMM's

### 2. Cipher Suite Incompatibility
- **Hypothesis**: c3270's cipher suites don't match AT-TLS policy requirements
- **Evidence**: AT-TLS policies often restrict allowed cipher suites
- **Test**: Compare cipher suites offered by c3270 vs PCOMM

### 3. Client Certificate Presentation
- **Hypothesis**: AT-TLS expects client certificate, but c3270 presents it incorrectly
- **Evidence**: Port 923 may require client cert for ELF authentication
- **Test**: Verify client certificate configuration in c3270

### 4. SNI (Server Name Indication) Issue
- **Hypothesis**: c3270 sends wrong/missing SNI, AT-TLS rejects connection
- **Evidence**: AT-TLS policies can require specific SNI values
- **Test**: Check SNI sent by c3270 vs PCOMM

## Port Comparison

### Port 992 (Regular TLS) - WORKS
- Standard TLS without AT-TLS policy enforcement
- c3270 connects successfully
- No ELF support

### Port 923 (ELF with AT-TLS) - FAILS
- AT-TLS policy enforced
- Stricter TLS requirements
- ELF authentication enabled
- c3270 fails at TLS init
- PCOMM succeeds

## Next Steps

### 1. Capture Network Traffic
```bash
# On z/OS (if possible)
tcpdump -i any -s 0 -w /tmp/port923.pcap port 923

# Or on client side
tcpdump -i any -s 0 -w port923.pcap host 9.47.80.126 and port 923
```

### 2. Compare TLS Handshakes
- Capture PCOMM successful connection
- Capture c3270 failed connection
- Compare ClientHello messages:
  - TLS version offered
  - Cipher suites
  - Extensions (SNI, ALPN, etc.)
  - Client certificate presentation

### 3. Check AT-TLS Policy
```
# On z/OS, check AT-TLS policy for port 923
# Look for:
# - TTLSRule for port 923
# - TTLSGroupAction with HandshakeRole Server
# - TTLSEnvironmentAction with TLS version and cipher requirements
```

### 4. Test c3270 TLS Configuration
Try forcing specific TLS versions:
```bash
# If c3270 supports TLS version selection
c3270 -elf TSOVS01 -tls-version 1.2 std1:923
```

### 5. Enable c3270 TLS Debug
Check if c3270 has TLS debug options:
```bash
c3270 -elf TSOVS01 -trace -ssl-debug std1:923
```

## Workaround Options

### Option 1: Relax AT-TLS Policy
If you control the z/OS AT-TLS policy, temporarily relax requirements:
- Allow TLS 1.2 and 1.3
- Expand allowed cipher suites
- Make client certificate optional

### Option 2: Configure c3270 TLS
If c3270 has TLS configuration options:
- Force TLS 1.2
- Specify compatible cipher suites
- Configure client certificate properly

### Option 3: Use Port 992 for Testing
Temporarily test ELF protocol on port 992 (if possible):
- Validates ELF implementation separate from AT-TLS issues
- Confirms CONNECT field fix works
- Isolates TLS problem

## References

- IBM z/OS Communications Server: IP Configuration Guide (AT-TLS)
- IBM z/OS Communications Server: IP Diagnosis Guide (Error 1030-01)
- RFC 5246: TLS 1.2 Specification
- RFC 8446: TLS 1.3 Specification

## Timeline

- **18:20:25**: First c3270 attempt, failed with 1030-01
- **18:23:23**: Second attempt, failed with 1030-01
- **18:29:01**: Third attempt (traced), failed with 1030-01
- **17:59:24**: PCOMM successful connection (for comparison)

All c3270 attempts fail within 12-18 seconds at TLS handshake initialization.