# OpenSSL s_client Success - c3270 Comparison

## Critical Discovery

**OpenSSL s_client successfully connects to port 923 with TLS 1.2**, proving:
- â Server configuration is correct
- â Certificates are valid
- â TLS 1.2 works
- â Client certificate is accepted
- â **Problem is specific to c3270**

## OpenSSL Test Results

### Command
```bash
openssl s_client -connect 9.47.80.126:923 -tls1_2 \
  -cert /tmp/fultonm_cert.pem \
  -key /tmp/fultonm_key.pem \
  -CAfile /tmp/STD1_server.pem \
  -showcerts
```

### Result: â SUCCESS

```
CONNECTED(00000003)
Protocol: TLSv1.2
Cipher: ECDHE-RSA-AES128-GCM-SHA256
Verification: OK
Verify return code: 0 (ok)
```

### Server Certificate
```
Subject: O=z/OS, OU=TN3270 Server, CN=STD1
Issuer: O=z/OS, OU=TN3270 Server, CN=STD1 (self-signed)
Valid: Mar 26 2026 - Jan 1 2031
```

### Client Certificate Accepted
```
Acceptable client certificate CA names:
- C=US, O=International Business Machines, OU=ZOSVSI, CN=SYSTEM_VS01TelnetCert
- C=US, O=International Business Machines, OU=ZOSVSI, CN=9.47.80.126_SELF_CACERT
- O=z/OS, OU=TN3270 Server, CN=STD1
- C=US, O=Express Logon Client, CN=FULTONM  â Our client cert CA
```

### Warning Message
```
Can't use SSL_get_servername
```

This warning suggests SNI (Server Name Indication) might be an issue.

## Comparison: OpenSSL vs c3270

| Aspect | OpenSSL s_client | c3270 |
|--------|------------------|-------|
| TCP Connection | â Succeeds | â Succeeds |
| TLS Handshake | â Completes | â Hangs |
| TLS Version | TLS 1.2 | TLS 1.2 (forced) |
| Cipher Suite | ECDHE-RSA-AES128-GCM-SHA256 | Unknown (never negotiated) |
| Client Cert | â Accepted | â Never sent? |
| Server Cert | â Verified | â Never received? |
| Result | â Connected | â Error 1030-01 |

## Root Cause Hypothesis

### Theory: c3270 TLS Initialization Issue

**Evidence**:
1. OpenSSL works with same certificates
2. c3270 hangs before any TLS data exchange
3. Server error occurs at "query or init HS" (handshake initialization)
4. c3270 trace shows no data received after TCP connection

**Possible Causes**:

#### 1. SNI (Server Name Indication) Issue
- OpenSSL warning: "Can't use SSL_get_servername"
- c3270 may not be sending SNI correctly
- AT-TLS may require specific SNI value

#### 2. TLS Extension Incompatibility
- c3270 may send TLS extensions that AT-TLS doesn't support
- AT-TLS may reject connection before handshake starts

#### 3. Application-Controlled TLS Timing
- AT-TLS config: `ApplicationControlled On`
- c3270 may not be calling TLS initialization at the right time
- OpenSSL s_client handles this differently

#### 4. Certificate Presentation Timing
- c3270 may present client certificate too early or too late
- AT-TLS expects specific timing for client cert

## Recommended Next Steps

### 1. Enable c3270 TLS Debug (if available)

Check if c3270 has TLS debug options:
```bash
c3270 -help | grep -i tls
c3270 -help | grep -i ssl
c3270 -help | grep -i debug
```

### 2. Compare TLS ClientHello Messages

Capture network traffic to compare:

**OpenSSL ClientHello**:
```bash
sudo tcpdump -i any -s 0 -w /tmp/openssl.pcap host 9.47.80.126 and port 923 &
openssl s_client -connect 9.47.80.126:923 -tls1_2 \
  -cert /tmp/fultonm_cert.pem \
  -key /tmp/fultonm_key.pem \
  -CAfile /tmp/STD1_server.pem
```

**c3270 ClientHello**:
```bash
sudo tcpdump -i any -s 0 -w /tmp/c3270.pcap host 9.47.80.126 and port 923 &
c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 -port 923 \
  -cafile /tmp/STD1_server.pem \
  -certfile /tmp/fultonm_cert.pem \
  -keyfile /tmp/fultonm_key.pem \
  STD1
```

Then compare with Wireshark:
- TLS version offered
- Cipher suites
- Extensions (SNI, ALPN, etc.)
- Client certificate presentation

### 3. Check c3270 TLS Implementation

c3270 uses OpenSSL (from build info):
```
Build options: --enable-local-process --without-readline --with-curses-wide --with-iconv
```

Check c3270's OpenSSL usage in source:
- `suite3270-4.4/Common/sio_openssl.c`
- Look for SSL_CTX initialization
- Check if SNI is set: `SSL_set_tlsext_host_name()`
- Check certificate loading timing

### 4. Test with Simplified AT-TLS Config

Temporarily modify port 923 AT-TLS config to match port 992:

```
# In pagttls.conf, change port 923 to:
TTLSEnvironmentAction EnvironmentActionTN3270
{
  HandshakeRole ServerWithClientAuth
  EnvironmentUserInstance 0              â Change from 1 to 0
  TTLSKeyringParms
  {
    Keyring SYSTEM/TELNET_RING
  }
  TTLSEnvironmentAdvancedParms
  {
    ApplicationControlled On
    TLSv1   Off
    TLSv1.1 Off
    TLSv1.2 On
    # Remove CertificateLabel line
    # Remove HandshakeTimeout line
  }
  # Keep same cipher suites
}
```

Then restart TCPIP and test c3270.

### 5. Check c3270 Source for SNI

Search c3270 source for SNI handling:
```bash
grep -r "SSL_set_tlsext_host_name\|SNI\|server.*name" suite3270-4.4/Common/
```

If c3270 doesn't set SNI, this could be the issue.

## Key Differences: Port 992 vs Port 923

| Configuration | Port 992 (Works) | Port 923 (Fails) |
|---------------|------------------|------------------|
| User Instance | 0 | 1 |
| Certificate Label | None | "TN3270 Server" |
| Trace Level | 1 | 255 |
| Handshake Timeout | Default | 600 seconds |
| Job Binding | None | TN3270 only |

**Hypothesis**: User Instance 1 or Certificate Label requirement causes c3270 to fail.

## Conclusion

**The problem is NOT**:
- â TLS version (TLS 1.2 works with OpenSSL)
- â Certificates (valid and accepted by server)
- â Server configuration (OpenSSL connects successfully)
- â Cipher suites (ECDHE-RSA-AES128-GCM-SHA256 works)

**The problem IS**:
- â **c3270-specific TLS initialization issue**
- â **Likely SNI or TLS extension incompatibility**
- â **Possibly related to ApplicationControlled TLS mode**
- â **May be related to User Instance or Certificate Label requirements**

**Next Action**: Capture and compare TLS ClientHello messages from OpenSSL vs c3270 to identify the exact difference.

## References

- **OpenSSL Test**: Successful TLS 1.2 connection
- **c3270 Trace**: /tmp/x3trc.16778499 (hangs after TCP connection)
- **Server Logs**: Error 1030-01 at handshake initialization
- **AT-TLS Config**: pagttls.conf lines 588-634