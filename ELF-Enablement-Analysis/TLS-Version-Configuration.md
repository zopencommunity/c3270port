# c3270 TLS Version Configuration Guide

## Problem

Port 923 on z/OS requires **TLS 1.2 ONLY** (configured in AT-TLS policy), but c3270 may be attempting to negotiate TLS 1.3, causing the handshake to fail with error 1030-01.

## Solution: Force c3270 to Use TLS 1.2

c3270 supports TLS version configuration through command-line options:

### Command-Line Options

```bash
-tlsminprotocol <version>    # Set minimum TLS protocol version
-tlsmaxprotocol <version>    # Set maximum TLS protocol version
```

### Supported Protocol Versions

From [`suite3270-4.4/Common/sioc.c`](suite3270-4.4/Common/sioc.c) lines 60-67:

| Version String | Alternative Names | Protocol |
|----------------|-------------------|----------|
| `SSL2` | `SSL2.0`, `SSL2_0` | SSL 2.0 |
| `SSL3` | `SSL3.0`, `SSL3_0` | SSL 3.0 |
| `TLS1` | `TLS1.0`, `TLS1_0` | TLS 1.0 |
| `TLS1.1` | `TLS1_1` | TLS 1.1 |
| `TLS1.2` | `TLS1_2` | **TLS 1.2** â Required for port 923 |
| `TLS1.3` | `TLS1_3` | TLS 1.3 |

## Testing Commands

### Test 1: Force TLS 1.2 Only (Recommended)

```bash
c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 \
  -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 \
  -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1
```

**Expected Result**: TLS handshake should succeed on port 923

### Test 2: Allow TLS 1.2 and Below

```bash
c3270 -trace -model 2 -secure \
  -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 \
  -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1
```

**Note**: Only sets maximum, allows any version up to TLS 1.2

### Test 3: Verify Current TLS Version (Diagnostic)

First, let's see what version c3270 is currently trying to use:

```bash
# Test without version restriction
c3270 -trace -model 2 -secure \
  -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1 2>&1 | grep -i "tls\|ssl\|protocol"
```

## Implementation Details

### How c3270 Handles TLS Versions

From [`suite3270-4.4/Common/sio_openssl.c`](suite3270-4.4/Common/sio_openssl.c) lines 506-518:

```c
proto_error = sioc_parse_protocol_min_max(
    config->min_protocol,    // From -tlsminprotocol
    config->max_protocol,    // From -tlsmaxprotocol
    SIP_SSL3,               // Default minimum: SSL 3.0
    -1,                     // Default maximum: Latest supported
    &min_protocol,
    &max_protocol
);

if (min_protocol >= 0) {
    SSL_CTX_set_min_proto_version(s->ctx, proto_map[min_protocol]);
}
if (max_protocol >= 0) {
    SSL_CTX_set_max_proto_version(s->ctx, proto_map[max_protocol]);
}
```

**Key Points**:
- If no options specified, c3270 uses SSL 3.0 as minimum and latest TLS as maximum
- On modern systems, "latest" is likely TLS 1.3
- z/OS port 923 requires exactly TLS 1.2

### Configuration Structure

From [`suite3270-4.4/include/tls_config.h`](suite3270-4.4/include/tls_config.h) lines 33-52:

```c
typedef struct {
    char *accept_hostname;
    bool verify_host_cert;
    bool starttls;
    char *ca_dir;
    char *ca_file;
    char *cert_file;
    char *cert_file_type;
    char *chain_file;
    char *key_file;
    char *key_file_type;
    char *key_passwd;
    char *client_cert;
    char *min_protocol;    // â Set by -tlsminprotocol
    char *max_protocol;    // â Set by -tlsmaxprotocol
    char *security_level;
} tls_config_t;
```

## z/OS Port 923 Requirements

From [`pagttls.conf`](../TSOExpressLogon/V2/ReferenceSystems/9_47_80_126System_NewConfigs/pagttls.conf) lines 616-622:

```
TTLSEnvironmentAdvancedParms
{
  TLSv1 Off       â TLS 1.0 disabled
  TLSv1.1 Off     â TLS 1.1 disabled
  TLSv1.2 On      â TLS 1.2 ONLY
  ApplicationControlled On
  HandshakeTimeout 600
  SecondaryMap Off
  CertificateLabel TN3270 Server
  ClientAuthType Required
}
```

**Server Requirements**:
- â TLS 1.2 ONLY
- â TLS 1.0 NOT allowed
- â TLS 1.1 NOT allowed
- â TLS 1.3 NOT allowed

## Verification Steps

### Step 1: Test with OpenSSL

Before testing c3270, verify the server accepts TLS 1.2:

```bash
# Test TLS 1.2 (should work)
openssl s_client -connect std1:923 -tls1_2 \
  -cert ${CERT_ROOT}/fultonm_cert.pem \
  -key ${CERT_ROOT}/fultonm_key.pem \
  -CAfile ${CERT_ROOT}/STD1_server.pem \
  -showcerts

# Test TLS 1.3 (should fail)
openssl s_client -connect std1:923 -tls1_3 \
  -cert ${CERT_ROOT}/fultonm_cert.pem \
  -key ${CERT_ROOT}/fultonm_key.pem \
  -CAfile ${CERT_ROOT}/STD1_server.pem \
  -showcerts
```

### Step 2: Test c3270 with TLS 1.2

```bash
c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 \
  -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 \
  -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1
```

### Step 3: Check Trace File

Look for TLS version in the trace:

```bash
grep -i "tls\|protocol\|handshake" /tmp/x3trc.*
```

Expected to see:
- TLS 1.2 negotiation
- Successful handshake
- TN3270E DEVICE-TYPE negotiation

### Step 4: Verify Server Logs

Check TN3270 server logs for successful connection:

```bash
ssh fultonm_9_47_80_126 "export PATH=\"/usr/lpp/IBM/zoautil/bin:\$PATH\" && \
  export LIBPATH=\"/usr/lpp/IBM/zoautil/lib:\$LIBPATH\" && \
  pjdd STC00036 JESMSGLG | tail -50"
```

Expected to see:
- Connection accepted on port 923
- TN3270E negotiation (not error 1030-01)
- Session established

## Alternative: X Resources Configuration

For persistent configuration, add to `~/.x3270pro`:

```
c3270.tlsMinProtocol: TLS1.2
c3270.tlsMaxProtocol: TLS1.2
```

Then run without command-line options:

```bash
c3270 -trace -model 2 -secure \
  -elf TSOVS01 \
  -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1
```

## Troubleshooting

### Issue: "Unknown protocol version"

**Error**: c3270 doesn't recognize the protocol version string

**Solution**: Use exact strings from the table above:
- â `TLS1.2` or `TLS1_2`
- â `TLS 1.2` (spaces not allowed)
- â `TLSv1.2` (wrong format)

### Issue: Still getting error 1030-01

**Possible causes**:
1. TLS version still wrong (check trace file)
2. Cipher suite mismatch (see next section)
3. Certificate label issue (see AT-TLS-Configuration-Analysis.md)
4. Client certificate format problem

**Next steps**:
1. Verify TLS 1.2 in trace file
2. Check cipher suites (see below)
3. Verify server certificate label exists

## Cipher Suite Compatibility

Port 923 allows only these cipher suites (from pagttls.conf lines 627-633):

```
V3CipherSuites TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
V3CipherSuites TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
V3CipherSuites TLS_RSA_WITH_AES_128_GCM_SHA256
V3CipherSuites TLS_RSA_WITH_AES_256_GCM_SHA384
```

c3270 (using OpenSSL) should support these by default, but if issues persist, check:

```bash
# List c3270's supported ciphers
openssl ciphers -v 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:AES128-GCM-SHA256:AES256-GCM-SHA384'
```

## Expected Outcome

With `-tlsminprotocol TLS1.2 -tlsmaxprotocol TLS1.2`:

1. â TLS handshake succeeds on port 923
2. â No error 1030-01 in server logs
3. â TN3270E negotiation proceeds
4. â DEVICE-TYPE REQUEST with CONNECT TSOVS01 sent
5. â Server accepts and routes to TSO pool
6. â ELF authentication proceeds

## Complete Test Command

```bash
# Full command with TLS 1.2 forced
c3270 -trace -model 2 -secure \
  -tlsminprotocol TLS1.2 \
  -tlsmaxprotocol TLS1.2 \
  -elf TSOVS01 \
  -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1

# Check trace file
ls -lt /tmp/x3trc.* | head -1
grep "DEVICE-TYPE\|CONNECT\|TLS" /tmp/x3trc.* | tail -20
```

## References

- **c3270 Source**: suite3270-4.4/Common/sio_openssl.c (TLS version handling)
- **Configuration**: suite3270-4.4/include/tls_config.h (tls_config_t structure)
- **Protocol Constants**: suite3270-4.4/Common/sioc.c (protocol version table)
- **AT-TLS Policy**: pagttls.conf (port 923 TLS requirements)
- **Command-Line Options**: suite3270-4.4/include/resources.h (option definitions)

## Next Steps After TLS Fix

Once TLS 1.2 handshake succeeds:

1. Verify DEVICE-TYPE REQUEST includes CONNECT TSOVS01
2. Check server accepts pool routing
3. Test ELF token transmission
4. Verify automatic TSO logon
5. Complete ELF implementation testing