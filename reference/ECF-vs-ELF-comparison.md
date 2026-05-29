# ECF vs ELF: Certificate-Based Authentication Comparison

## ECF (Enterprise Certificate Framework)

### Authentication Flow
1. **TLS Handshake**: Client presents certificate during TLS handshake
2. **Certificate Validation**: Host validates certificate against RACF RACDCERT
3. **Automatic Login**: User bypasses TSO logon screen entirely
4. **Direct to READY**: User goes straight to TSO READY prompt

### Key Characteristics
- â No logon screen displayed
- â No user interaction required
- â Authentication during TLS handshake
- â Certificate-to-userid mapping in RACF
- â Fully automatic

### Protocol Details
- Certificate presented in TLS ClientCertificate message
- RACF CERTMAP associates certificate with TSO userid
- No application-layer authentication needed
- User sees TSO READY prompt immediately

## ELF (Enhanced Logon Facility)

### Authentication Flow (Based on PCOMM Documentation)
1. **TLS Handshake**: Client presents certificate during TLS handshake
2. **TN3270E Negotiation**: Client sends ELF Application ID
3. **Logon Screen**: User DOES see TSO logon screen
4. **ELF Tokens**: Client sends `)USR.ID(` and `)PSS.WD(` tokens
5. **Token Processing**: Server extracts credentials from certificate

### Key Characteristics
- â ï¸ Logon screen IS displayed
- â ï¸ Requires ELF Application ID
- â ï¸ Uses special tokens instead of actual credentials
- â ï¸ Semi-automatic (tokens sent automatically, but screen appears)

### Protocol Details (Hypothesis)
- Certificate presented in TLS ClientCertificate message
- ELF Application ID sent during TN3270E negotiation (how?)
- Logon screen displayed normally
- Client sends `)USR.ID(` token â Server extracts userid from certificate
- Client sends `)PSS.WD(` token â Server extracts password from certificate
- Server authenticates using certificate-derived credentials

## Key Differences

| Aspect | ECF | ELF |
|--------|-----|-----|
| **Logon Screen** | Bypassed | Displayed |
| **User Interaction** | None | Tokens sent automatically |
| **Application ID** | Not used | Required (e.g., TSOVS01) |
| **Authentication Point** | TLS handshake only | TLS + Application layer |
| **Token Usage** | No tokens | `)USR.ID(` and `)PSS.WD(` |
| **RACF Integration** | RACDCERT CERTMAP | ELF Application ID mapping |

## Critical Question: How is ELF Application ID Sent?

### Hypothesis 1: In CONNECT Field (Current Implementation)
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT TSOVS01
```
**Problem**: Server rejects with INV-NAME

### Hypothesis 2: In CONNECT Field with Prefix
```
DEVICE-TYPE REQUEST IBM-3278-2-E CONNECT (ELF) TSOVS01
```
**Problem**: Server still rejects with INV-NAME

### Hypothesis 3: Not in CONNECT Field at All
- Maybe ELF Application ID is NOT sent in TN3270E negotiation
- Maybe it's configured on the server side only
- Maybe it's derived from the certificate itself
- Maybe it's sent through a different mechanism

### Hypothesis 4: Sent After Connection Established
- PCOMM calls `SetELFApplID` AFTER `WaitForAppAvailable`
- This suggests it might be sent AFTER TN3270E negotiation completes
- Maybe through a separate TN3270E subnegotiation
- Maybe using TN3270E_OP_ASSOCIATE operation

## What We Know from PCOMM

```vbscript
autECLSession.autECLOIA.WaitForAppAvailable  # Wait for connection
autECLSession.SetELFApplID "TSOVS01"         # Set Application ID
autECLSession.autECLOIA.WaitForInputReady    # Wait for ready
autECLSession.autECLPS.SendKeys ")USR.ID("   # Send userid token
```

**Key Observation**: `SetELFApplID` is called AFTER the connection is established, not during initial negotiation.

## Possible Solutions

### Option 1: Don't Send Application ID in DEVICE-TYPE
- Send DEVICE-TYPE REQUEST without CONNECT field
- Let server determine Application ID from certificate
- Application ID might be in certificate CN or SAN

### Option 2: Send Application ID After DEVICE-TYPE
- Complete DEVICE-TYPE negotiation normally
- Send Application ID through separate TN3270E subnegotiation
- Use TN3270E_OP_ASSOCIATE or custom operation

### Option 3: Application ID is Server-Side Only
- Application ID configured on server, not sent by client
- Server maps certificate to Application ID
- Client just presents certificate and sends tokens

## Next Steps

1. **Test without CONNECT field**: See if server accepts connection
2. **Capture PCOMM traffic**: Get actual protocol trace from working PCOMM session
3. **Check IBM documentation**: Find ELF-specific TN3270E protocol docs
4. **Test with different Application IDs**: Maybe "TSOVS01" is wrong

## Conclusion

ELF appears to be a **hybrid approach** between full automatic authentication (ECF) and traditional password login:
- Uses TLS client certificates for identity
- Shows logon screen (unlike ECF)
- Uses special tokens instead of passwords
- Requires ELF Application ID (purpose unclear)

The critical missing piece is: **How is the ELF Application ID actually communicated to the server?**