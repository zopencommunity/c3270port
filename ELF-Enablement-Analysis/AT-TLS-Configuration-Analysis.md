# AT-TLS Configuration Analysis - Port 992 vs Port 923

## Configuration Files

- **TN3270 Config**: `/Users/fultonm/Documents/Development/TSOExpressLogon/V2/ReferenceSystems/9_47_80_126System_NewConfigs/tn3270.cfg`
- **AT-TLS Policy**: `/Users/fultonm/Documents/Development/TSOExpressLogon/V2/ReferenceSystems/9_47_80_126System_NewConfigs/pagttls.conf`

## TN3270 Server Configuration

### Port 992 Configuration (Lines 8-12)
```
TelnetParms
  Port 992
  LUSESSIONPEND
  MSG07
EndTelnetParms
```
- Standard TLS port
- No ExpressLogon
- Basic session handling

### Port 923 Configuration (Lines 14-20)
```
TelnetParms
  TTLSPort 923
  ConnType Secure
  Debug Detail
  ExpressLogon          â ELF ENABLED
  MSG07
EndTelnetParms
```
- **TTLSPort**: Uses AT-TLS (Application Transparent TLS)
- **ExpressLogon**: ELF certificate-based authentication enabled
- **Debug Detail**: Enhanced logging

### VTAM Configuration (Lines 22-29)
```
BeginVTAM
  Port 992 923
  DEFAULTAPPL TSO
  DEFAULTLUS
    TCP00001..TCP00030
  ENDDEFAULTLUS
  ALLOWAPPL *
EndVTAM
```
- Both ports use same LU pool (TCP00001-TCP00030)
- Default application: TSO
- No pool routing configured (explains INV-NAME rejection)

## AT-TLS Policy Comparison

### Port 992 AT-TLS Rule (Lines 330-380)

**TTLSRule tn_serv** (Lines 330-338):
```
TTLSRule tn_serv
{
  LocalAddr All
  LocalPortRange 992
  Direction Inbound
  TTLSGroupActionRef tn_grp_act
  TTLSEnvironmentActionRef tn_env_act
  TTLSConnectionActionRef tn_conn_act
}
```

**TTLSEnvironmentAction tn_env_act** (Lines 346-368):
```
TTLSEnvironmentAction tn_env_act
{
  HandshakeRole ServerWithClientAuth    â Requires client cert
  EnvironmentUserInstance 0
  TTLSKeyringParms
  {
    Keyring SYSTEM/TELNET_RING
  }
  TTLSEnvironmentAdvancedParms
  {
    ApplicationControlled On            â App controls TLS
    TLSv1   Off
    TLSv1.1 Off
    TLSv1.2 On                          â TLS 1.2 ONLY
  }
  TTLSCipherParms
  {
    V3CipherSuites TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
    V3CipherSuites TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    V3CipherSuites TLS_RSA_WITH_AES_128_GCM_SHA256
    V3CipherSuites TLS_RSA_WITH_AES_256_GCM_SHA384
  }
}
```

### Port 923 AT-TLS Rule (Lines 588-634)

**TTLSRule TN3270SecurePort** (Lines 591-598):
```
TTLSRule TN3270SecurePort
{
  LocalPortRange 923
  Direction Inbound
  Jobname TN3270                        â Specific to TN3270 job
  TTLSGroupActionRef GroupActionTN3270
  TTLSEnvironmentActionRef EnvironmentActionTN3270
}
```

**TTLSGroupAction GroupActionTN3270** (Lines 600-605):
```
TTLSGroupAction GroupActionTN3270
{
  TTLSEnabled On
  Trace 255                             â MAXIMUM TRACE LEVEL
  GroupUserInstance 1
}
```

**TTLSEnvironmentAction EnvironmentActionTN3270** (Lines 607-634):
```
TTLSEnvironmentAction EnvironmentActionTN3270
{
  HandshakeRole ServerWithClientAuth    â Requires client cert
  CtraceClearText Off
  TTLSKeyringParms
  {
    Keyring SYSTEM/TELNET_RING
  }
  EnvironmentUserInstance 1
  TTLSEnvironmentAdvancedParms
  {
    TLSv1 Off
    TLSv1.1 Off
    TLSv1.2 On                          â TLS 1.2 ONLY
    ApplicationControlled On            â App controls TLS
    HandshakeTimeout 600                â 10 MINUTE TIMEOUT
    SecondaryMap Off
    CertificateLabel TN3270 Server      â Specific cert label
    ClientAuthType Required             â Client cert REQUIRED
  }
  TTLSCipherParms
  {
    V3CipherSuites TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
    V3CipherSuites TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    V3CipherSuites TLS_RSA_WITH_AES_128_GCM_SHA256
    V3CipherSuites TLS_RSA_WITH_AES_256_GCM_SHA384
  }
}
```

## Key Differences

| Feature | Port 992 | Port 923 |
|---------|----------|----------|
| **TLS Type** | Regular TLS | AT-TLS (Application Transparent) |
| **ELF Support** | No | Yes (ExpressLogon) |
| **Trace Level** | 1 | 255 (Maximum) |
| **Handshake Timeout** | Default | 600 seconds |
| **Certificate Label** | None | "TN3270 Server" |
| **Job Binding** | None | TN3270 job only |
| **User Instance** | 0 | 1 |

## ð Root Cause of Port 923 TLS Failure

### Error 1030-01 Analysis

The server logs show:
```
RCODE: 1030-01  TTLS Ioctl failed for query or init HS.
PARM1: FFFFFFFF PARM2: 00000464 PARM3: 77B77221
```

**PARM2: 0x00000464 = 1124 decimal**

This is likely an errno value. Common z/OS errno 1124 meanings:
- Certificate validation failure
- Client certificate not presented
- TLS version mismatch
- Cipher suite negotiation failure

### Critical Configuration Differences

**Port 923 has STRICTER requirements**:

1. **Jobname Binding** (Line 595)
   ```
   Jobname TN3270
   ```
   - Rule only applies to TN3270 job
   - If job name doesn't match, rule doesn't apply
   - Could cause handshake to fail

2. **Certificate Label** (Line 624)
   ```
   CertificateLabel TN3270 Server
   ```
   - Requires specific certificate in keyring
   - If certificate not found, handshake fails

3. **User Instance** (Lines 604, 615)
   ```
   GroupUserInstance 1
   EnvironmentUserInstance 1
   ```
   - Different instance than port 992 (which uses 0)
   - May affect certificate/keyring access

4. **Maximum Trace** (Line 603)
   ```
   Trace 255
   ```
   - Full debugging enabled
   - Should provide detailed logs

## ð¯ Why PCOMM Works but c3270 Fails

### Hypothesis 1: TLS Version Negotiation
- **Both ports**: TLS 1.2 ONLY (TLSv1.2 On, others Off)
- **PCOMM**: Likely negotiates TLS 1.2 correctly
- **c3270**: May be requesting TLS 1.3 or 1.1

**Test**: Check c3270's TLS version preference
```bash
openssl s_client -connect std1:923 -tls1_2 -showcerts
```

### Hypothesis 2: Cipher Suite Mismatch
**Allowed Cipher Suites** (same for both ports):
- TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
- TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
- TLS_RSA_WITH_AES_128_GCM_SHA256
- TLS_RSA_WITH_AES_256_GCM_SHA384

**PCOMM**: Likely offers compatible cipher suites
**c3270**: May offer different cipher suites

**Test**: Check c3270's cipher suite list
```bash
openssl s_client -connect std1:923 -cipher 'ECDHE-RSA-AES128-GCM-SHA256'
```

### Hypothesis 3: Client Certificate Presentation
**Both ports require**: `HandshakeRole ServerWithClientAuth`

**PCOMM**: Presents client certificate correctly
**c3270**: May present certificate in wrong format or at wrong time

**Your command includes**:
```bash
-certfile ${CERT_ROOT}/fultonm_cert.pem
-keyfile ${CERT_ROOT}/fultonm_key.pem
```

**Possible issues**:
- Certificate format (PEM vs DER)
- Certificate chain incomplete
- Private key format
- Certificate not trusted by server

### Hypothesis 4: Certificate Label Mismatch
Port 923 requires:
```
CertificateLabel TN3270 Server
```

**Check**: Does SYSTEM/TELNET_RING contain a certificate labeled "TN3270 Server"?

If not, AT-TLS cannot find the server certificate and handshake fails.

## ð§ Recommended Fixes

### Fix 1: Verify Server Certificate Label
```
# On z/OS
RACDCERT LIST(LABEL('TN3270 Server')) ID(SYSTEM)
RACDCERT LISTRING(TELNET_RING) ID(SYSTEM)
```

If "TN3270 Server" certificate doesn't exist:
- Create it, OR
- Change pagttls.conf line 624 to match existing certificate label

### Fix 2: Check AT-TLS Logs
With Trace 255 enabled, check:
```
# On z/OS
D TCPIP,,TTLS,CONN,DETAIL
```

Look for:
- Certificate validation errors
- TLS version negotiation failures
- Cipher suite mismatches

### Fix 3: Test with OpenSSL
```bash
# Test TLS 1.2 connection
openssl s_client -connect std1:923 -tls1_2 \
  -cert ${CERT_ROOT}/fultonm_cert.pem \
  -key ${CERT_ROOT}/fultonm_key.pem \
  -CAfile ${CERT_ROOT}/STD1_server.pem \
  -showcerts -debug

# Check what cipher suites are offered
openssl s_client -connect std1:923 -tls1_2 -cipher 'ALL' -showcerts
```

### Fix 4: Simplify Port 923 Configuration (Temporary)
To isolate the issue, temporarily make port 923 match port 992:

```
# In pagttls.conf, change port 923 to match port 992:
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

## ð Pool Routing Issue (Port 992)

### Why "TSOVS01" is Rejected as INV-NAME

**VTAM Configuration** (Lines 22-29):
```
BeginVTAM
  Port 992 923
  DEFAULTAPPL TSO
  DEFAULTLUS
    TCP00001..TCP00030    â LU pool, NOT application pool
  ENDDEFAULTLUS
  ALLOWAPPL *
EndVTAM
```

**Problem**: No pool routing configured
- `DEFAULTLUS` defines LU names, not application pools
- "TSOVS01" is not recognized as a valid resource name
- Server expects specific LU names (TCP00001-TCP00030) or generic request

**Solution**: Use generic DEVICE-TYPE REQUEST (no CONNECT field) on port 992:
```bash
c3270 -trace -model 2 -secure -port 992 STD1
# Don't use -elf option on port 992
```

**For ELF with pool routing**: Must use port 923 once TLS issue is resolved

## ð¯ Action Plan

### Priority 1: Fix Port 923 TLS Handshake
1. Verify "TN3270 Server" certificate exists in SYSTEM/TELNET_RING
2. Check AT-TLS trace logs (Trace 255 is enabled)
3. Test with OpenSSL to isolate c3270 vs server issue
4. Compare c3270 TLS configuration with PCOMM

### Priority 2: Test ELF on Port 923
Once TLS works:
```bash
c3270 -trace -model 2 -secure -elf TSOVS01 -port 923 \
  -cafile ${CERT_ROOT}/STD1_server.pem \
  -certfile ${CERT_ROOT}/fultonm_cert.pem \
  -keyfile ${CERT_ROOT}/fultonm_key.pem \
  STD1
```

Expected result:
- TLS handshake succeeds
- DEVICE-TYPE REQUEST with CONNECT TSOVS01 sent
- Server accepts and routes to TSO pool
- ELF authentication proceeds

### Priority 3: Complete ELF Implementation
- Test ELF token transmission
- Verify automatic TSO logon
- Test certificate-based authentication

## ð References

- **IBM z/OS Communications Server**: IP Configuration Guide (AT-TLS)
- **IBM z/OS Communications Server**: IP Diagnosis Guide (Error 1030-01)
- **TN3270 Configuration**: tn3270.cfg
- **AT-TLS Policy**: pagttls.conf
- **Server Logs**: TN3270 job STC00036 JESMSGLG

## Timeline

- **May 20, 2026**: Port 923 AT-TLS configuration added
- **May 29, 2026**: c3270 TLS handshake failures discovered
- **May 29, 2026**: Configuration analysis completed
- **Next**: Resolve certificate label and TLS negotiation issues