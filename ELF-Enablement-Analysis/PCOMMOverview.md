# PCOMM ELF Connection with Macro

## Overview

This document describes how to use IBM Personal Communications (PCOMM) to connect to z/OS using Enhanced Logon Facility (ELF) with an automated macro script.

## Prerequisites

### z/OS Configuration

**CRITICAL REQUIREMENT**: The z/OS system MUST be configured with:
```
PASSWORDPREPROMPT(OFF)
```

This setting has been configured on the target z/OS system. Without this setting, the ELF macro will not work correctly because the system will prompt for password before the macro can send the credentials.

### PCOMM Setup

- IBM Personal Communications installed
- Session configured to connect to the z/OS system
- Macro support enabled in PCOMM

## ELF Macro Script

### Script Header

```vbscript
[PCOMM SCRIPT HEADER]
LANGUAGE=VBSCRIPT
DESCRIPTION=ELF Mike
```

### Complete Macro Code

```vbscript
[PCOMM SCRIPT SOURCE]
OPTION EXPLICIT
autECLSession.SetConnectionByName(ThisSessionName)
REM This line calls the macro subroutine
subSub1_

sub subSub1_()
   autECLSession.autECLOIA.WaitForAppAvailable
   
   ' Set the ELF Application ID
   autECLSession.SetELFApplID "TSOVS01"
   autECLSession.autECLOIA.WaitForInputReady
   
   ' Send User ID
   autECLSession.autECLPS.SendKeys ")USR.ID("
   autECLSession.autECLOIA.WaitForInputReady
   autECLSession.autECLPS.SendKeys "[enter]"
   
   ' Wait for password prompt
   autECLSession.autECLPS.WaitForAttrib 8,19,"0c","3c",3,10000
   autECLSession.autECLPS.WaitForCursor 8,20,10000
   autECLSession.autECLOIA.WaitForAppAvailable
   
   ' Send Password
   autECLSession.autECLOIA.WaitForInputReady
   autECLSession.autECLPS.SendKeys ")PSS.WD("
   autECLSession.autECLOIA.WaitForInputReady
   autECLSession.autECLPS.SendKeys "[enter]"
end sub
```

## How the Macro Works

### Understanding the Flow: Client vs Server Actions

**Key Actors**:
- **PCOMM Client** (or c3270) - The 3270 emulator running on your desktop/workstation
- **TN3270 Server** - The z/OS Communications Server (VTAM/TCPIP) handling TN3270 protocol
- **z/OS ELF** - Enhanced Logon Facility running on z/OS, processing ELF tokens
- **TSO/VTAM** - The target application on z/OS (e.g., TSOVS01)

**Communication Flow**:
```
[PCOMM/c3270 Client] <--TN3270 Protocol--> [TN3270 Server] <--> [z/OS ELF] <--> [TSO/VTAM]
     (Desktop)              (Network)           (z/OS)          (z/OS)        (z/OS)
```

**Direction Notation**:
- **CLIENT â SERVER**: Client sends data to z/OS
- **SERVER â CLIENT**: z/OS sends screen data to client
- **CLIENT WAITS**: Client waits for server response

### Step-by-Step Execution

#### 1. **Initialize Session** (CLIENT ACTION)
```vbscript
autECLSession.SetConnectionByName(ThisSessionName)
```
**Who**: PCOMM Client
**What**: Establishes TCP connection to z/OS TN3270 server
**Direction**: CLIENT â SERVER (connection request)

#### 2. **Wait for System Ready** (CLIENT WAITS)
```vbscript
autECLSession.autECLOIA.WaitForAppAvailable
```
**Who**: PCOMM Client (waiting)
**What**: Waits for z/OS to complete TN3270 negotiation and present initial screen
**Direction**: SERVER â CLIENT (screen data arrives)
**Result**: Client receives initial logon screen from z/OS

#### 3. **Set ELF Application ID** (CLIENT ACTION)
```vbscript
autECLSession.SetELFApplID "TSOVS01"
```
**Who**: PCOMM Client
**What**: Sends ELF Application ID during TN3270E negotiation
**Direction**: CLIENT â SERVER (TN3270E subnegotiation)
**Purpose**: Tells z/OS ELF which application to connect to (TSO/VTAM application ID)

#### 4. **Send User ID** (CLIENT â SERVER)

**First, z/OS presents the User ID prompt** (SERVER â CLIENT):
- After Step 3 (SetELFApplID), z/OS sends the initial logon screen
- Screen displays: "USERID ===> _____" (or similar)
- Cursor positioned at the User ID input field
- Client waits for this screen (via WaitForInputReady in Step 3)

**Then, client sends User ID token** (CLIENT â SERVER):
```vbscript
autECLSession.autECLPS.SendKeys ")USR.ID("
autECLSession.autECLPS.SendKeys "[enter]"
```
**Who**: PCOMM Client sends
**What**: Sends ELF user ID token to z/OS
**Direction**: CLIENT â SERVER (keyboard input)
**Format**: `)USR.ID(` - This is an ELF token, not the actual user ID
**Processing on z/OS**:
- z/OS ELF receives the token
- ELF extracts actual user ID from client certificate
- ELF validates user ID with RACF
- z/OS prepares password prompt screen

#### 5. **Wait for Password Prompt** (CLIENT WAITS)
```vbscript
autECLSession.autECLPS.WaitForAttrib 8,19,"0c","3c",3,10000
autECLSession.autECLPS.WaitForCursor 8,20,10000
autECLSession.autECLOIA.WaitForAppAvailable
```
**Who**: PCOMM Client (waiting)
**What**: Waits for z/OS to process user ID and present password prompt
**Direction**: SERVER â CLIENT (screen update with password prompt)
**Details**:
- Waits for specific screen attributes at row 8, column 19
- Waits for cursor to appear at row 8, column 20
- Timeout: 10 seconds
**What Happened on z/OS**:
1. z/OS ELF received `)USR.ID(` token
2. ELF extracted user ID from client certificate
3. ELF validated user ID with RACF
4. z/OS sent password prompt screen to client

#### 6. **Send Password** (CLIENT â SERVER)
```vbscript
autECLSession.autECLPS.SendKeys ")PSS.WD("
autECLSession.autECLPS.SendKeys "[enter]"
```
**Who**: PCOMM Client sends
**What**: Sends ELF password token to z/OS
**Direction**: CLIENT â SERVER (keyboard input)
**Format**: `)PSS.WD(` - This is an ELF token, not the actual password
**Processing**:
- z/OS ELF receives the token
- ELF extracts password/passticket from client certificate
- ELF validates password with RACF
- If successful, z/OS logs user into TSO/VTAM application

## ELF Token Format

### User ID Token
```
)USR.ID(
```
- Instructs ELF to use the user ID from the client certificate
- No actual user ID is transmitted in the macro

### Password Token
```
)PSS.WD(
```
- Instructs ELF to use the password from the certificate passticket
- No actual password is transmitted in the macro

## Security Considerations

### Certificate-Based Authentication

- **User credentials are NOT stored in the macro**
- User ID and password are extracted from the client certificate
- Certificate must be properly configured in RACF
- Certificate must be mapped to a valid z/OS user ID

### PASSWORDPREPROMPT(OFF) Requirement

With `PASSWORDPREPROMPT(OFF)`:
- System does not prompt for password before ELF processes the tokens
- Allows the macro to send both user ID and password tokens in sequence
- Required for automated ELF logon to work correctly

With `PASSWORDPREPROMPT(ON)` (not compatible):
- System would prompt for password immediately after user ID
- Macro timing would be disrupted
- ELF tokens would not be processed correctly

## Configuration Steps

### 1. Configure PCOMM Session

1. Open PCOMM Session Configuration
2. Set connection parameters:
   - Host: z/OS system IP/hostname
   - Port: TN3270 port (typically 23 or 992 for TLS)
   - Terminal type: IBM-3278-2 or similar

### 2. Enable TLS/SSL (if required)

1. In PCOMM Session Configuration:
   - Enable SSL/TLS
   - Configure client certificate
   - Set certificate store location

### 3. Install the Macro

1. Open PCOMM Macro Editor
2. Create new macro
3. Paste the complete script (header + source)
4. Save with descriptive name (e.g., "ELF_Auto_Logon.mac")

### 4. Assign Macro to Session

1. In PCOMM Session Configuration:
   - Go to Automation tab
   - Set "Auto-start macro" to the saved macro
   - Or assign to a keyboard shortcut

## Testing the Macro

### Manual Test

1. Start PCOMM session
2. Run the macro manually from Macro menu
3. Observe the logon sequence
4. Verify successful TSO logon

### Automated Test

1. Configure macro to auto-start with session
2. Start PCOMM session
3. Macro should execute automatically
4. Verify successful TSO logon without manual intervention

## Troubleshooting

### Common Issues

**Macro fails at password prompt:**
- Verify `PASSWORDPREPROMPT(OFF)` is configured on z/OS
- Check screen position coordinates (row 8, column 19-20)
- Increase timeout values if system is slow

**Certificate not recognized:**
- Verify client certificate is installed in PCOMM
- Check certificate is mapped to user ID in RACF
- Verify certificate is not expired

**ELF tokens not processed:**
- Verify ELF is enabled on z/OS
- Check TSOVS01 application ID is correct
- Review z/OS ELF configuration

**Timing issues:**
- Increase `WaitForAttrib` timeout (currently 10000ms)
- Add additional `WaitForInputReady` calls
- Check network latency

## References

- IBM Personal Communications User's Guide
- IBM z/OS Communications Server: IP Configuration Guide
- IBM RACF Security Administrator's Guide
- ELF (Enhanced Logon Facility) documentation

## Notes

- This macro is designed for automated TSO logon via ELF
- Requires proper certificate configuration in both PCOMM and RACF
- The `PASSWORDPREPROMPT(OFF)` setting is critical for this workflow
- Screen coordinates (row 8, column 19-20) may vary by installation