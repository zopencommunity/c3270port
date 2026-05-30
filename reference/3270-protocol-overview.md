# 3270 Protocol Overview (TCP/IP/TLS)

## Connection Initiation

**Session Establishment:**
- Client initiates TCP connection to host on port 23 (Telnet) or 992 (TLS)
- Three-way TCP handshake: SYN, SYN-ACK, ACK
- TLS handshake (if port 992): Certificate exchange, cipher negotiation, key establishment
- Telnet negotiation using IAC (Interpret As Command) sequences
- Terminal type negotiation: Client sends TERMINAL-TYPE option
- Host and client negotiate 3270 data stream support

**Key Negotiation Options:**
- TERMINAL-TYPE: Identifies emulator capabilities (e.g., IBM-3278-2, IBM-3279-3)
- BINARY: Enables 8-bit data transmission
- EOR (End of Record): Marks logical message boundaries
- TN3270E: Enables extended protocol features (device names, response handling)

**TN3270E Extended Negotiation:**
- DEVICE-TYPE: Negotiates specific device name
- FUNCTIONS: Negotiates protocol functions (BIND-IMAGE, DATA-STREAM-CTL, RESPONSES, SCS-CTL-CODES, SYSREQ)
- Connection confirmation or rejection

## General Data Transfer

**TCP/IP Transport:**
- Reliable, ordered byte stream delivery
- Flow control via TCP window mechanism
- Congestion control algorithms
- Retransmission on packet loss
- TLS encryption (if enabled): AES-256, ChaCha20, or negotiated cipher

**Data Stream Architecture:**
- Block-mode protocol: Entire screen transmitted as single unit
- Uses EBCDIC encoding for character data
- Structured Field format: Command + WCC (Write Control Character) + Orders + Data
- EOR marker delimits logical messages

**Outbound Stream (Host to Terminal):**
- Write commands: W (Write), EW (Erase/Write), EWA (Erase/Write Alternate)
- WCC controls: Reset MDT, unlock keyboard, sound alarm, reset partition
- Orders: SBA (Set Buffer Address), SF (Start Field), IC (Insert Cursor)
- Attribute bytes: Define field properties (protected, numeric, hidden, intensified)
- Screen buffer: 1920 characters (24x80) or 3440 characters (43x80)

**Inbound Stream (Terminal to Host):**
- AID (Attention Identifier): Indicates which key triggered transmission
- Cursor address: Current cursor position
- Modified fields only: Only fields with MDT (Modified Data Tag) transmitted
- Efficient: Reduces network traffic by sending only changed data

**Field Attributes:**
- Protected vs. unprotected (user input allowed)
- Numeric vs. alphanumeric
- Display attributes: normal, intensified, hidden
- MDT (Modified Data Tag): Marks fields for transmission

**3270 Data Stream Orders:**
- SBA: Position data at specific screen location
- SF: Start new field with attributes
- SFE: Start Field Extended (color, highlighting, validation)
- SA: Set Attribute (modify current field)
- IC: Insert Cursor
- PT: Program Tab
- RA: Repeat to Address
- EUA: Erase Unprotected to Address

## Connection Termination

**Normal Termination:**
- Application sends logoff command
- Host sends final screen update
- TCP connection closed with FIN packets
- Four-way handshake: FIN, ACK, FIN, ACK
- TLS close_notify alert (if TLS enabled)
- Session resources deallocated on host

**Abnormal Termination:**
- Network failure: TCP timeout or connection reset
- Client disconnect: RST packet or immediate socket close
- Host detects broken connection through TCP keepalive or write failure
- TLS alert messages for protocol errors
- Session cleanup on host side
- Uncommitted work may be lost

**TN3270E Enhanced Termination:**
- UNBIND request notification
- Proper session cleanup signaling
- Device name released for reuse
- Better error reporting through TN3270E response codes

## Protocol Characteristics

**TCP/IP Performance Features:**
- Block-mode reduces round trips (vs. character-mode terminals)
- Modified field transmission minimizes bandwidth
- TCP Nagle algorithm may be disabled for responsiveness
- Local editing: Cursor movement, field validation without host interaction
- Attention keys: Immediate host notification (Enter, PF keys, PA keys)

**TLS Security Features:**
- Port 992: TLS encryption from connection start
- Certificate-based server authentication
- Optional client certificate authentication
- Cipher suite negotiation (TLS 1.2/1.3)
- Perfect forward secrecy with ephemeral keys
- Protection against eavesdropping and tampering

**Basic TN3270 Security Limitations:**
- Port 23: Clear-text transmission
- No built-in authentication (relies on application layer)
- Credentials transmitted in clear (if not using TLS)
- Session hijacking possible without encryption
- Man-in-the-middle attacks possible

**Key Differences: TN3270 vs TN3270E:**
- TN3270E adds device naming capability
- Enhanced response handling and error codes
- Better error recovery mechanisms
- Support for printer sessions
- BIND image negotiation
- Sysreq and Attn key support

## Common AID Keys

- Enter: Submit data to host
- PF1-PF24: Program Function keys (application-defined)
- PA1-PA3: Program Attention keys (interrupt, no data sent)
- Clear: Clear screen and reset
- Sysreq: System request (TN3270E)

## Network Considerations

**Latency Impact:**
- Block-mode design minimizes round trips
- Single transaction per user action
- Network delay affects perceived responsiveness
- Local field editing masks network latency

**Bandwidth Efficiency:**
- Only modified fields transmitted
- Typical transaction: 100-500 bytes
- Screen refresh: 2-4 KB maximum
- Efficient for low-bandwidth connections

**Firewall/NAT Traversal:**
- Standard TCP ports (23, 992)
- Stateful connections work through NAT
- Long-lived sessions may require keepalive
- TLS works transparently through proxies

---

# TLS 3270 Data Flow: TSO Login â ISPF â Logoff

## Phase 1: Connection Establishment

**TCP/TLS Handshake (Client â Host, Port 992):**
```
1. Client â Host: TCP SYN
2. Host â Client: TCP SYN-ACK
3. Client â Host: TCP ACK
4. Client â Host: TLS ClientHello (cipher suites, TLS version)
5. Host â Client: TLS ServerHello, Certificate, ServerHelloDone
6. Client â Host: ClientKeyExchange, ChangeCipherSpec, Finished
7. Host â Client: ChangeCipherSpec, Finished
   [TLS tunnel established - all subsequent data encrypted]
```

**Telnet/TN3270 Negotiation:**
```
8. Host â Client: IAC DO TERMINAL-TYPE
9. Client â Host: IAC WILL TERMINAL-TYPE
10. Host â Client: IAC SB TERMINAL-TYPE SEND IAC SE
11. Client â Host: IAC SB TERMINAL-TYPE IS IBM-3278-2 IAC SE
12. Host â Client: IAC DO EOR
13. Client â Host: IAC WILL EOR
14. Host â Client: IAC DO BINARY
15. Client â Host: IAC WILL BINARY
16. Host â Client: IAC WILL BINARY
17. Client â Host: IAC DO BINARY
18. Host â Client: IAC DO TN3270E
19. Client â Host: IAC WILL TN3270E
    [3270 data stream ready]
```

## Phase 2: TSO Login

**Initial Screen Display:**
```
20. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Orders: SBA, SF (protected fields for "TSO/E LOGON" screen)
    Data: "TSO/E LOGON", "Userid ====>", "Password ====>", etc.
    Screen buffer: 1920 bytes (24x80)
```

**User Enters Credentials:**
```
21. User types: USERID in userid field
22. User types: PASSWORD in password field (hidden attribute)
23. User presses: ENTER key
```

**Login Submission:**
```
24. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Cursor Address: (row, col where cursor was)
    Modified Fields:
      - Field 1 (Userid): SBA + "USERID"
      - Field 2 (Password): SBA + "PASSWORD"
    Total: ~50-100 bytes
```

**TSO Welcome Screen:**
```
25. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Orders: SBA, SF (multiple fields)
    Data: "ICH70001I USERID LAST ACCESS AT hh:mm:ss ON date"
          "***"
          "READY"
    Screen: TSO READY prompt displayed
```

## Phase 3: Enter ISPF

**User Starts ISPF:**
```
26. User types: ISPF
27. User presses: ENTER
```

**ISPF Command Submission:**
```
28. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Cursor Address: (command line position)
    Modified Field: SBA + "ISPF"
    Total: ~30 bytes
```

**ISPF Primary Option Menu:**
```
29. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Orders: Multiple SBA, SF, SFE (extended attributes for colors)
    Data: "ISPF Primary Option Menu"
          "0  Settings"
          "1  View"
          "2  Edit"
          "3  Utilities"
          [... menu options ...]
          "Option ===>"
    Screen: Full ISPF menu (2-3 KB with attributes)
```

## Phase 4: Immediate Logoff

**User Exits ISPF:**
```
30. User types: X (or =X)
31. User presses: ENTER
```

**Exit Command Submission:**
```
32. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Cursor Address: (option field)
    Modified Field: SBA + "X"
    Total: ~25 bytes
```

**Return to TSO READY:**
```
33. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Data: "***"
          "READY"
    Screen: Back to TSO prompt
```

**User Logs Off:**
```
34. User types: LOGOFF
35. User presses: ENTER
```

**Logoff Submission:**
```
36. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Modified Field: SBA + "LOGOFF"
    Total: ~30 bytes
```

**Logoff Confirmation:**
```
37. Host â Client: [EOR]
    Command: ERASE/WRITE
    Data: "IKJ56455I userid LOGGED OFF TSO AT hh:mm:ss ON date"
    Screen: Logoff message displayed
```

## Phase 5: Connection Termination

**Normal Disconnect:**
```
38. Host â Client: TLS close_notify alert
39. Client â Host: TLS close_notify alert
40. Host â Client: TCP FIN
41. Client â Host: TCP ACK
42. Client â Host: TCP FIN
43. Host â Client: TCP ACK
    [Connection closed, session resources released]
```

## Data Flow Summary

**Total Messages:**
- TCP/TLS Setup: 7 packets
- Telnet Negotiation: 12 exchanges
- TSO Login: 3 screen updates, 2 user inputs
- ISPF Entry: 2 screen updates, 1 user input
- Logoff: 2 screen updates, 2 user inputs
- Termination: 6 packets

**Bandwidth Usage:**
- Connection setup: ~5 KB (certificates, negotiation)
- TSO login screen: ~2 KB
- User credentials: ~100 bytes
- ISPF menu: ~3 KB
- Exit commands: ~50 bytes each
- Logoff message: ~200 bytes
- Total session: ~11 KB

**Key Characteristics:**
- All data encrypted within TLS tunnel
- Block-mode: Full screens sent, only modified fields returned
- Efficient: User input typically 25-100 bytes
- Interactive: Each ENTER key triggers immediate host response
- Stateful: Host maintains session context throughout

---

# ECF Certificate-Based Authentication Flow: Automatic TSO Login â ISPF â Logoff

## Phase 1: Connection Establishment with Client Certificate

**TCP/TLS Handshake with Mutual Authentication (Client â Host, Port 992):**
```
1. Client â Host: TCP SYN
2. Host â Client: TCP SYN-ACK
3. Client â Host: TCP ACK
4. Client â Host: TLS ClientHello (cipher suites, TLS version)
5. Host â Client: TLS ServerHello, Certificate, CertificateRequest, ServerHelloDone
   [Host requests client certificate for mutual authentication]
6. Client â Host: Certificate (client cert), ClientKeyExchange, CertificateVerify, ChangeCipherSpec, Finished
   [Client presents certificate signed by trusted CA]
7. Host â Client: ChangeCipherSpec, Finished
   [TLS tunnel established with mutual authentication]
   [Host validates client certificate against RACF/SAF]
```

**Telnet/TN3270 Negotiation:**
```
8. Host â Client: IAC DO TERMINAL-TYPE
9. Client â Host: IAC WILL TERMINAL-TYPE
10. Host â Client: IAC SB TERMINAL-TYPE SEND IAC SE
11. Client â Host: IAC SB TERMINAL-TYPE IS IBM-3278-2 IAC SE
12. Host â Client: IAC DO EOR
13. Client â Host: IAC WILL EOR
14. Host â Client: IAC DO BINARY
15. Client â Host: IAC WILL BINARY
16. Host â Client: IAC WILL BINARY
17. Client â Host: IAC DO BINARY
18. Host â Client: IAC DO TN3270E
19. Client â Host: IAC WILL TN3270E
    [3270 data stream ready]
```

## Phase 2: Automatic TSO Login (No User Interaction)

**ECF Authentication and Automatic Login:**
```
20. Host validates client certificate:
    - Certificate chain verification against trusted CA
    - Certificate not expired or revoked (CRL/OCSP check)
    - Subject DN or SAN matches RACF user mapping
    - RACF RACDCERT CERTMAP associates cert with TSO userid
    
21. Host performs automatic authentication:
    - No TSO logon screen displayed
    - No password required
    - RACF authenticates user based on certificate
    - TSO session established automatically
    
22. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Orders: SBA, SF (multiple fields)
    Data: "ICH70001I USERID LAST ACCESS AT hh:mm:ss ON date"
          "***"
          "READY"
    Screen: TSO READY prompt displayed immediately
    [User bypasses logon screen entirely]
```

**Key Differences from Password Login:**
- No logon screen displayed (steps 20-24 from password flow eliminated)
- No userid/password entry required
- Authentication happens during TLS handshake
- User goes directly to TSO READY prompt
- Faster login: ~2 seconds vs ~5-10 seconds

## Phase 3: Enter ISPF

**User Starts ISPF:**
```
23. User types: ISPF
24. User presses: ENTER
```

**ISPF Command Submission:**
```
25. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Cursor Address: (command line position)
    Modified Field: SBA + "ISPF"
    Total: ~30 bytes
```

**ISPF Primary Option Menu:**
```
26. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Orders: Multiple SBA, SF, SFE (extended attributes for colors)
    Data: "ISPF Primary Option Menu"
          "0  Settings"
          "1  View"
          "2  Edit"
          "3  Utilities"
          [... menu options ...]
          "Option ===>"
    Screen: Full ISPF menu (2-3 KB with attributes)
```

## Phase 4: Immediate Logoff

**User Exits ISPF:**
```
27. User types: X (or =X)
28. User presses: ENTER
```

**Exit Command Submission:**
```
29. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Cursor Address: (option field)
    Modified Field: SBA + "X"
    Total: ~25 bytes
```

**Return to TSO READY:**
```
30. Host â Client: [EOR]
    Command: ERASE/WRITE
    WCC: Unlock keyboard, reset MDT
    Data: "***"
          "READY"
    Screen: Back to TSO prompt
```

**User Logs Off:**
```
31. User types: LOGOFF
32. User presses: ENTER
```

**Logoff Submission:**
```
33. Client â Host: [EOR]
    AID: ENTER (0x7D)
    Modified Field: SBA + "LOGOFF"
    Total: ~30 bytes
```

**Logoff Confirmation:**
```
34. Host â Client: [EOR]
    Command: ERASE/WRITE
    Data: "IKJ56455I userid LOGGED OFF TSO AT hh:mm:ss ON date"
    Screen: Logoff message displayed
```

## Phase 5: Connection Termination

**Normal Disconnect:**
```
35. Host â Client: TLS close_notify alert
36. Client â Host: TLS close_notify alert
37. Host â Client: TCP FIN
38. Client â Host: TCP ACK
39. Client â Host: TCP FIN
40. Host â Client: TCP ACK
    [Connection closed, session resources released]
```

## ECF Data Flow Summary

**Total Messages:**
- TCP/TLS Setup with Client Cert: 7 packets (includes certificate exchange)
- Telnet Negotiation: 12 exchanges
- Automatic TSO Login: 1 screen update (no user input)
- ISPF Entry: 2 screen updates, 1 user input
- Logoff: 2 screen updates, 2 user inputs
- Termination: 6 packets

**Bandwidth Usage:**
- Connection setup: ~8 KB (includes client certificate ~2-3 KB)
- Automatic login: 0 bytes user input (vs ~100 bytes password flow)
- TSO welcome screen: ~2 KB
- ISPF menu: ~3 KB
- Exit commands: ~50 bytes each
- Logoff message: ~200 bytes
- Total session: ~13 KB (vs ~11 KB password flow)

**Key Characteristics:**
- Mutual TLS authentication (client and server certificates)
- No password transmission (even encrypted)
- Automatic authentication during TLS handshake
- User bypasses TSO logon screen
- Faster login experience
- Certificate-based identity mapping in RACF
- Enhanced security: No password to compromise

---

# Comparison: Password-Based vs Certificate-Based Authentication

## Authentication Flow Differences

| Aspect | Password-Based Login | ECF Certificate-Based Login |
|--------|---------------------|----------------------------|
| **TLS Handshake** | Server certificate only | Mutual authentication (client + server certs) |
| **Authentication Point** | Application layer (TSO logon screen) | TLS layer (during handshake) |
| **User Interaction** | Manual userid/password entry | Automatic (no user input) |
| **Logon Screen** | Displayed, requires input | Bypassed entirely |
| **Credential Type** | Password (knowledge factor) | Certificate (possession factor) |
| **Credential Storage** | User memory or password manager | Certificate store (hardware token, keychain) |
| **Network Transmission** | Password sent in 3270 data stream (encrypted) | Certificate sent in TLS handshake |

## Security Comparison

| Security Aspect | Password-Based | Certificate-Based |
|----------------|----------------|-------------------|
| **Credential Compromise** | Password can be phished, guessed, or stolen | Certificate requires private key theft (harder) |
| **Brute Force Attack** | Vulnerable to password guessing | Not applicable (cryptographic authentication) |
| **Credential Reuse** | Users may reuse passwords | Certificates are unique per user/device |
| **Revocation** | Password change required | Certificate revocation (CRL/OCSP) |
| **Multi-Factor** | Single factor (knowledge) | Can combine with hardware token (possession) |
| **Audit Trail** | Login attempts logged | Certificate serial number logged |
| **Password Expiry** | Requires periodic password changes | Certificate expiry (typically 1-3 years) |

## Performance Comparison

| Performance Metric | Password-Based | Certificate-Based |
|-------------------|----------------|-------------------|
| **Connection Setup** | ~5 KB (server cert only) | ~8 KB (client + server certs) |
| **Login Time** | 5-10 seconds (user types credentials) | 2-3 seconds (automatic) |
| **User Actions** | 2 (type userid, type password) | 0 (automatic) |
| **Screen Updates** | 3 (logon screen, welcome, ready) | 1 (welcome/ready only) |
| **Network Round Trips** | 2 (display logon, submit credentials) | 0 (no logon screen) |
| **Total Bandwidth** | ~11 KB | ~13 KB |

## Implementation Requirements

### Password-Based Login Requirements:
- TLS server certificate
- RACF password authentication
- TSO logon application
- Password policy enforcement
- Password expiry management

### Certificate-Based Login Requirements:
- TLS server certificate
- Client certificate infrastructure
- Certificate Authority (CA) for issuing client certs
- RACF RACDCERT configuration
- Certificate-to-userid mapping (CERTMAP)
- Certificate revocation infrastructure (CRL/OCSP)
- AT-TLS policy for client certificate requirement
- Certificate distribution mechanism
- Hardware token support (optional but recommended)

## User Experience Comparison

### Password-Based Login:
1. User sees TSO logon screen
2. User types userid
3. User types password (hidden)
4. User presses ENTER
5. Wait for authentication
6. TSO READY prompt appears

**Total: 4 user actions, ~5-10 seconds**

### Certificate-Based Login:
1. Connection established automatically
2. TSO READY prompt appears immediately

**Total: 0 user actions, ~2-3 seconds**

## Use Cases

### Password-Based Login Best For:
- Shared workstations
- Temporary access
- Guest users
- Simple deployment
- No PKI infrastructure
- Low security requirements

### Certificate-Based Login Best For:
- Personal workstations
- High security environments
- Automated processes
- Frequent logins
- Compliance requirements (PCI-DSS, HIPAA)
- Single sign-on (SSO) integration
- Passwordless authentication initiatives

## Migration Path

**Transitioning from Password to Certificate-Based:**

1. **Phase 1: Infrastructure Setup**
   - Deploy Certificate Authority
   - Configure RACF RACDCERT
   - Create certificate-to-userid mappings
   - Configure AT-TLS policies

2. **Phase 2: Pilot Deployment**
   - Issue certificates to pilot users
   - Test automatic login
   - Validate certificate revocation
   - Monitor audit logs

3. **Phase 3: Gradual Rollout**
   - Issue certificates to user groups
   - Maintain password fallback
   - Train users on certificate management
   - Monitor adoption metrics

4. **Phase 4: Full Deployment**
   - All users have certificates
   - Disable password authentication (optional)
   - Enforce certificate-only access
   - Implement certificate lifecycle management

## Summary

**Certificate-based authentication (ECF) provides:**
- â Stronger security (cryptographic vs password)
- â Faster login (automatic vs manual)
- â Better user experience (no typing)
- â Enhanced audit trail (certificate serial numbers)
- â Reduced password management overhead

**Trade-offs:**
- â ï¸ Higher initial setup complexity
- â ï¸ Requires PKI infrastructure
- â ï¸ Certificate lifecycle management
- â ï¸ Slightly higher bandwidth (~2 KB more)
- â ï¸ Hardware token costs (optional)

**Recommendation:** Certificate-based authentication is ideal for production environments with high security requirements and frequent user logins. Password-based authentication remains suitable for occasional access, shared systems, or environments without PKI infrastructure.