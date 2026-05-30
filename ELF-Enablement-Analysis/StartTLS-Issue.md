# STARTTLS vs Immediate TLS Issue

## Problem Identified

c3270 is configured with `startTls=true` which causes it to:
1. Connect in plain text
2. Wait for telnet negotiation
3. Then upgrade to TLS via STARTTLS

But z/OS port 923 is configured for **immediate TLS** (TLS from first byte), not STARTTLS.

## Evidence from Trace

```
startTls=true termName=
tls992=true tlsMaxProtocol=TLS1.2 tlsMinProtocol=TLS1.2
```

The connection hangs because:
- c3270 waits for telnet negotiation before starting TLS
- z/OS expects TLS immediately and sends TLS ServerHello
- Neither side proceeds because they're speaking different protocols

## Solution

Use the `-L` option to force immediate TLS (no STARTTLS):

```bash
c3270 -trace -model 2 -L \
  -elf TSOVS01 -port 923 \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -cafile /u/fultonm/Certificates/STD1_server.pem \
  -certfile /u/fultonm/Certificates/fultonm_cert.pem \
  -keyfile /u/fultonm/Certificates/fultonm_key.pem \
  STD1
```

The `-L` option:
- Disables STARTTLS
- Forces immediate TLS from first byte
- Matches z/OS port 923 configuration

## Port Configuration

### Port 992 (Standard TLS)
- Immediate TLS
- No STARTTLS
- Works with `-secure` or `-L`

### Port 923 (ELF with AT-TLS)
- Immediate TLS via AT-TLS
- No STARTTLS
- **Requires `-L` option**

## Why `-secure` Doesn't Work

The `-secure` option enables `startTls=true` by default, which:
- Works for port 992 (standard TLS port)
- **Fails for port 923** (AT-TLS expects immediate TLS)

## Correct Command

```bash
c3270 -trace -model 2 -L -elf TSOVS01 -port 923 \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -cafile /u/fultonm/Certificates/STD1_server.pem \
  -certfile /u/fultonm/Certificates/fultonm_cert.pem \
  -keyfile /u/fultonm/Certificates/fultonm_key.pem \
  STD1
```

## Expected Result

With `-L` option:
1. â TCP connection established
2. â TLS handshake starts immediately
3. â SNI sent in ClientHello (with our fix)
4. â TLS handshake completes
5. â TN3270E negotiation begins
6. â ELF protocol proceeds

## Related Issues

This explains why:
- OpenSSL s_client works (immediate TLS by default)
- c3270 with `-secure` fails (STARTTLS mode)
- Connection hangs waiting for data (protocol mismatch)

## References

- RFC 2817: Upgrading to TLS Within HTTP/1.1 (STARTTLS concept)
- c3270 documentation: `-L` option for immediate TLS
- AT-TLS configuration: Immediate TLS mode