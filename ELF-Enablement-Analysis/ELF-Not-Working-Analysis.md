# ELF Not Working - Root Cause Analysis

## The Problem

The ELF tokens `)USR.ID(` and `)PSS.WD(` are being **displayed on the terminal screen** instead of being processed by the server for automatic authentication.

**What the user sees:**
```
IKJ56700A ENTER USERID -
)USR.ID()PSS.WD(
IKJ56710I INVALID USERID, )USR.ID(
IKJ56703A REENTER THIS OPERAND -
```

**What SHOULD happen with ELF:**
- Server receives certificate-based authentication
- Server automatically logs in the user
- User sees TSO READY prompt
- **NO userid/password prompts appear**

## Why This Is Wrong

### ELF Should Be Transparent

When ELF is working correctly:
1. Client sends certificate during TLS handshake â (we're doing this)
2. Client sends IBMELF=YES and IBMAPPLID=TSOVS01 â (we're doing this)
3. **Server extracts userid from certificate** â (NOT happening)
4. **Server automatically authenticates** â (NOT happening)
5. **User goes directly to TSO READY** â (NOT happening)

### What's Actually Happening

1. TLS handshake succeeds â
2. IBMAPPLID sent correctly â
3. Server shows TSO logon screen â (should not appear)
4. c3270 sends ELF tokens as **keyboard input** â (wrong!)
5. Server treats tokens as literal text â (wrong!)

## Root Cause: Server Not Processing ELF

The server is **not recognizing** this as an ELF connection. Possible reasons:

### 1. Certificate Not Mapped to Userid

**Most Likely Issue**: The certificate might not be properly mapped to a userid in RACF.

**Check on z/OS:**
```
RACDCERT ID(FULTONM) LIST
```

Look for:
- Certificate label
- TRUST status
- CERTAUTH mapping

### 2. TN3270 Server Not Configured for ELF

**Check TN3270 configuration:**
```
Port 923 configuration in tn3270.cfg:
- ExpressLogon enabled?
- Certificate authentication enabled?
- Proper APPLID configured?
```

### 3. AT-TLS Not Passing Certificate Info

**Check AT-TLS configuration:**
```
pagttls.conf for port 923:
- ClientAuthType: Required or SAFCheck?
- CertificateLabel correct?
- Handshake parameters?
```

### 4. APPLID Mismatch

The CONNECT field "TSOVS01" might not match the configured APPLID in VTAM/TN3270.

## Evidence from Trace

### Line 108: IBMAPPLID Sent Correctly
```
SENT SB NEW-ENVIRON IS USERVAR "IBMELF" VALUE "YES" USERVAR "IBMAPPLID" VALUE "TSOVS01" SE
```
â Client is doing its part

### Line 138: TN3270E Rejected
```
RCVD SB TN3270E DEVICE-TYPE REJECT REASON INV-NAME SE
```
â Server rejects CONNECT field "TSOVS01"

### Line 214-215: TSO Logon Screen Appears
```
EraseWrite - TSO logon screen appears
'IKJ56700A ENTER USERID -'
```
â This should NOT appear with ELF

### Lines 228-251: Tokens Sent as Keyboard Input
```
Enter(2,9) SetBufferAddress(1,27) ')USR.ID('
Enter(2,17) SetBufferAddress(1,27) ')USR.ID()PSS.WD('
```
â c3270 is sending these as **keyboard input**, not as part of protocol negotiation

## The Real Problem

**c3270 is sending ELF tokens AFTER the TSO logon screen appears**, which means:
1. The server has already decided this is NOT an ELF connection
2. The server is treating this as a normal TSO logon
3. The tokens are being sent as literal keyboard input

**This is backwards!** ELF authentication should happen **BEFORE** any TSO screen appears.

## What PCOMM Does Differently

When PCOMM connects with ELF:
1. TLS handshake with certificate â
2. NEW-ENVIRON with IBMELF=YES and IBMAPPLID â
3. **Server recognizes certificate** â
4. **Server extracts userid from certificate** â
5. **Server automatically authenticates** â
6. **User sees TSO READY immediately** â
7. **NO logon screen appears** â

## Next Steps to Debug

### 1. Check Certificate Mapping on z/OS
```bash
ssh fultonm_9_47_80_126
RACDCERT ID(FULTONM) LIST
```

Look for the certificate and verify it's mapped to userid FULTONM.

### 2. Check TN3270 Server Configuration
```bash
cat /etc/tn3270.cfg
```

Look for port 923 configuration and verify ExpressLogon settings.

### 3. Check AT-TLS Configuration
```bash
cat /etc/pagttls.conf
```

Look for port 923 TTLSRule and verify certificate authentication settings.

### 4. Compare with PCOMM Trace

We need to see what PCOMM sends that makes the server recognize ELF.

### 5. Check VTAM APPLID Configuration

The APPLID "TSOVS01" might not be configured correctly in VTAM.

## Hypothesis

The most likely issue is that the **certificate is not properly mapped to a userid in RACF**, so the server cannot perform automatic authentication even though all the protocol negotiation is correct.

**Alternative hypothesis**: The TN3270 server configuration for port 923 might not have ExpressLogon properly enabled or configured.