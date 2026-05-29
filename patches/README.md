## Description of patches

This directory contains patches for implementing Enhanced Logon Facility (ELF) support in c3270.

### Patch Naming Convention

All patches follow the `<filename>.<ext>.patch` naming convention, with exactly one patch per source file. Patches can be applied in any order.

### Patch Descriptions

#### Pre-existing Fixes

**x3270if.c.patch**
- Adds missing `#include <termios.h>` to fix compilation on z/OS
- Required for terminal I/O operations

#### Phase 1: ELF Application ID Support

**appres.h.patch**
- Adds `elf` field to `appres` structure
- Stores the ELF Application ID (1-8 alphanumeric characters)

**resources.h.patch**
- Adds ELF resource definition for command-line and configuration file support
- Enables `-elf <applid>` command-line option

**telnet.c.patch**
- Implements ELF Application ID transmission during TN3270E negotiation
- Sends `SEND ELF <applid>` subnegotiation when ELF is configured
- Integrates with existing TN3270E protocol flow

**glue.h.patch**
- Adds function declarations for ELF support:
  - `elf_init()` - Initialize and validate ELF configuration
  - `elf_enable_processing()` - Enable automatic token transmission
  - `send_elf_token()` - Send ELF authentication tokens

**glue.c.patch**
- Implements `validate_elf_applid()` - Validates ELF Application ID format
- Implements `elf_init()` - Initializes ELF support with validation
- Implements `elf_enable_processing()` - Enables ELF state machine
- Implements `send_elf_token()` - Sends ELF tokens with Enter key

**host.c.patch**
- Calls `elf_init()` during connection initialization
- Ensures ELF is configured before connection attempt

#### Phase 2: ELF Automatic Token Transmission

**task.c.patch**
- Adds `#include "glue.h"` for ELF function declarations
- Implements ELF state machine with four states:
  - `ELF_DISABLED` - ELF not enabled
  - `ELF_SEND_USERID` - Ready to send User ID token
  - `ELF_SEND_PASSWORD` - Ready to send Password token
  - `ELF_COMPLETE` - Authentication complete
- Automatically sends `)USR.ID(` and `)PSS.WD(` tokens after screen updates
- Includes default case in switch statement for error handling

**sched.c.patch**
- Suppresses "unused variable" warning for platform-specific macro usage
- Adds `(void)i;` statement to indicate intentional usage

### ELF Protocol Overview

Enhanced Logon Facility (ELF) provides automatic authentication for z/OS applications using certificate-based credentials:

1. **Application ID Transmission** (Phase 1)
   - Client sends ELF Application ID during TN3270E negotiation
   - Server associates connection with ELF-enabled application

2. **Automatic Token Transmission** (Phase 2)
   - Client automatically sends `)USR.ID(` token after first screen update
   - Client automatically sends `)PSS.WD(` token after second screen update
   - Server extracts credentials from client certificate and completes authentication

### Testing

To test ELF support:

1. Configure ELF Application ID:
   ```bash
   c3270 -elf MYAPP hostname
   ```

2. Connect to ELF-enabled z/OS system with client certificate

3. Verify automatic authentication without manual credential entry

### References

- IBM z/OS Communications Server: IP Configuration Guide
- TN3270E Protocol (RFC 2355)
- Enhanced Logon Facility documentation
