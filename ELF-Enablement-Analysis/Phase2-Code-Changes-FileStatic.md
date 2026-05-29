# Phase 2: ELF Token Transmission - File-Static Implementation

## Overview

This document describes the **file-static implementation** for automatic ELF token transmission in c3270. This approach uses an enum-based state machine with file-static encapsulation for better software engineering practices.

## Design Philosophy

**Key Principles**:
1. **Enum for readability**: Use explicit state names (ELF_SEND_USERID vs numeric counters)
2. **File-static encapsulation**: Hide state variable in task.c to avoid global pollution
3. **Setter function**: Provide controlled initialization interface from glue.c
4. **Minimal complexity**: Only one extra function (5 lines) for encapsulation
5. **Semantic clarity**: State ends at ELF_COMPLETE (not reset to DISABLED)

## State Machine Design

### Enum Definition

```c
typedef enum {
    ELF_DISABLED = 0,      /* ELF not enabled */
    ELF_SEND_USERID,       /* Ready to send User ID token */
    ELF_SEND_PASSWORD,     /* Ready to send Password token */
    ELF_COMPLETE           /* Authentication complete */
} elf_state_t;
```

### State Transitions

```
Connection with ELF App ID
           â
    ELF_SEND_USERID âââ task_host_output() called (User ID screen)
           â                    â
      Send )USR.ID(        Press Enter
           â
    ELF_SEND_PASSWORD âââ task_host_output() called (Password screen)
           â                    â
      Send )PSS.WD(        Press Enter
           â
      ELF_COMPLETE (Done - no further action)
```

## Implementation Details

### File 1: glue.h (Header File)

**Location**: `suite3270-4.4/include/glue.h`

**Add after existing declarations** (around line 46):

```c
/* ELF functions */
void elf_enable_processing(void);               /* Enable ELF in task.c */
void send_elf_token(const char *token);         /* Helper in glue.c */
```

**Rationale**:
- Only function declarations in header (no enum needed)
- `elf_enable_processing()` enables ELF when valid Application ID is provided
- `send_elf_token()` centralizes token transmission logic
- Enum and state variable are private to task.c (better encapsulation)

### File 2: task.c (State Management)

**Location**: `suite3270-4.4/Common/task.c`

**Add to includes section** (around line 44):

```c
#include "glue.h"  /* For elf_state_t, elf_set_initial_state(), send_elf_token() */
```

**Add enum definition and file-static state variable** (around line 100, after other static variables):

```c
/**
 * ELF authentication states.
 *
 * This enum is private to task.c and not exposed in headers.
 */
typedef enum {
    ELF_DISABLED = 0,      /* ELF not enabled */
    ELF_SEND_USERID,       /* Ready to send User ID token */
    ELF_SEND_PASSWORD,     /* Ready to send Password token */
    ELF_COMPLETE           /* Authentication complete */
} elf_state_t;

/**
 * ELF authentication state (file-static for encapsulation).
 *
 * Tracks the progress of ELF (Enhanced Logon Facility) automatic authentication.
 * This variable is intentionally file-static to avoid global state pollution.
 *
 * Lifetime:
 * - Defaults to ELF_DISABLED
 * - Set to ELF_SEND_USERID via elf_enable_processing() when ELF is enabled
 * - Updated in task_host_output() as authentication progresses
 * - Ends at ELF_COMPLETE when authentication finishes
 *
 * Access:
 * - Enablement: elf_enable_processing() (called from glue.c:elf_init())
 * - State transitions: task_host_output() (within this file)
 */
static elf_state_t elf_state = ELF_DISABLED;
```

**Add enable function** (around line 120, after static variable):

```c
/**
 * Enable ELF automatic authentication processing.
 *
 * Called by elf_init() in glue.c when a valid ELF Application ID is configured.
 * Sets the state to ELF_SEND_USERID to begin automatic authentication.
 */
void
elf_enable_processing(void)
{
    elf_state = ELF_SEND_USERID;
}
```

**Modify task_host_output() function** (around line 3795):

Add this code block after the existing screen update processing, before the function returns:

```c
    /* ELF automatic token transmission */
    if (elf_state != ELF_DISABLED && elf_state != ELF_COMPLETE &&
        IN_3270 && CAN_PROCEED) {
        switch (elf_state) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");
                elf_state = ELF_SEND_PASSWORD;  /* Advance to password state */
                break;
                
            case ELF_SEND_PASSWORD:
                send_elf_token(")PSS.WD(");
                elf_state = ELF_COMPLETE;  /* Mark authentication complete */
                break;
        }
    }
```

**Rationale**:
- File-static variable provides encapsulation
- Setter function provides controlled initialization interface
- Direct state access within file for transitions (no function call overhead)
- Switch statement makes state transitions explicit and readable

### File 3: glue.c (Initialization and Helpers)

**Location**: `suite3270-4.4/Common/glue.c`

**Add send_elf_token() helper function** (after validate_elf_applid(), around line 545):

```c
/**
 * Send an ELF token to the host.
 * 
 * Converts the token string to UCS-4 format, sends it to the host,
 * and presses Enter to submit it.
 * 
 * @param token The ELF token string to send (e.g., ")USR.ID(" or ")PSS.WD(")
 */
void
send_elf_token(const char *token)
{
    size_t len = strlen(token);
    ucs4_t *ucs_token = (ucs4_t *)Malloc(len * sizeof(ucs4_t));
    
    /* Convert ASCII token to UCS-4 */
    for (size_t i = 0; i < len; i++) {
        ucs_token[i] = (ucs4_t)token[i];
    }
    
    /* Send token and press Enter */
    emulate_uinput(ucs_token, len, false);
    Free(ucs_token);
    key_AID(AID_ENTER);
}
```

**Modify elf_init() function** (existing function, around line 534):

```c
/**
 * Initialize ELF support.
 * 
 * Called during connection initialization to validate the ELF Application ID
 * and set the initial ELF authentication state.
 */
void
elf_init(void)
{
    const char *elf_applid = appres.elf_applid;
    
    /* If no ELF Application ID, state remains ELF_DISABLED (default) */
    if (elf_applid == NULL || *elf_applid == '\0') {
        return;
    }
    
    /* If invalid ELF Application ID, state remains ELF_DISABLED */
    if (!validate_elf_applid(elf_applid)) {
        popup_an_error("Invalid ELF Application ID: must be 1-8 alphanumeric characters");
        return;
    }
    
    /* Valid ELF Application ID - enable automatic authentication */
    elf_enable_processing();
}
```

**Rationale**:
- `send_elf_token()` centralizes token transmission logic
- `elf_init()` validates ELF Application ID and enables processing only when valid
- Default state is ELF_DISABLED (no function call needed for disabled case)
- Clear separation: validation in glue.c, state management in task.c

## Architecture Benefits

### Complete Encapsulation

**Enum and Variable in task.c**:
```c
// task.c - Everything private to this file
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

static elf_state_t elf_state = ELF_DISABLED;
```

**Benefits**:
- â Enum not exposed in headers (complete encapsulation)
- â State hidden from other modules
- â No global namespace pollution
- â Clear ownership (task.c owns everything)
- â Easier to reason about state changes

### Controlled Enablement

**Enable Function**:
```c
void elf_enable_processing(void) {
    elf_state = ELF_SEND_USERID;
}
```

**Benefits**:
- â Clear enablement interface (only called when ELF is valid)
- â Default state is ELF_DISABLED (no function call needed)
- â Simpler than generic setter (no state parameter needed)
- â Only 4 lines of code

### Direct Access for Transitions

**Within task.c**:
```c
elf_state = ELF_SEND_PASSWORD;  // â Direct access (no function call)
```

**Benefits**:
- â No function call overhead for state transitions
- â Simple and readable
- â Fast (called on every screen update)

## Code Size Summary

| Component | Lines of Code |
|-----------|---------------|
| Function declarations (glue.h) | 2 lines |
| Enum definition (task.c) | 6 lines |
| File-static variable + docs (task.c) | 20 lines |
| Enable function + docs (task.c) | 8 lines |
| send_elf_token() + docs (glue.c) | 15 lines |
| Modified elf_init() (glue.c) | 12 lines |
| task_host_output() logic (task.c) | 15 lines |
| **Total** | **~38 lines** |

**Comparison**:
- Global variable approach: ~40 lines
- File-static approach: ~38 lines
- **Difference**: Fewer lines AND better encapsulation â

## Implementation Checklist

- [ ] Add `elf_enable_processing()` declaration to `glue.h`
- [ ] Add `send_elf_token()` declaration to `glue.h`
- [ ] Add `#include "glue.h"` to `task.c`
- [ ] Add enum definition to `task.c` (private to file)
- [ ] Add file-static `elf_state` variable to `task.c` (defaults to ELF_DISABLED)
- [ ] Implement `elf_enable_processing()` in `task.c`
- [ ] Add switch statement to `task_host_output()` in `task.c`
- [ ] Implement `send_elf_token()` in `glue.c`
- [ ] Modify `elf_init()` to call `elf_enable_processing()` only when valid
- [ ] Test compilation on desktop
- [ ] Test compilation on z/OS
- [ ] Test with ELF-enabled z/OS system

## Testing Strategy

### Unit Testing

1. **State Initialization**:
   - Verify state defaults to ELF_DISABLED when no ELF App ID
   - Verify `elf_enable_processing()` called only when valid ELF App ID
   - Verify state is file-static (not accessible from other modules)

2. **State Transitions**:
   - Verify SEND_USERID â SEND_PASSWORD after first screen
   - Verify SEND_PASSWORD â COMPLETE after second screen
   - Verify COMPLETE â DISABLED after third screen

3. **Token Transmission**:
   - Verify `)USR.ID(` sent in SEND_USERID state
   - Verify `)PSS.WD(` sent in SEND_PASSWORD state
   - Verify Enter key pressed after each token

### Integration Testing

1. Connect to ELF-enabled z/OS system
2. Verify automatic login without user interaction
3. Verify state transitions occur in correct order
4. Verify no tokens sent after authentication complete

## Error Handling

**Existing Error Cases** (from Phase 1):
- Invalid ELF Application ID â popup error, call `elf_set_initial_state(ELF_DISABLED)`
- No ELF Application ID â silently call `elf_set_initial_state(ELF_DISABLED)`

**New Error Cases**:
- If `CAN_PROCEED` is false â Skip token transmission (wait for next screen update)
- If not `IN_3270` â Skip token transmission (wrong mode)

**Recovery**:
- State machine is self-contained
- If token transmission fails, worst case is user must login manually
- No system instability or crashes

## Advantages Over Global Variable

| Aspect | Global Variable | File-Static + Setter |
|--------|----------------|----------------------|
| **Encapsulation** | Low | **High** â |
| **Namespace Pollution** | Yes | **No** â |
| **Clear Ownership** | Unclear | **Clear** â |
| **Initialization Interface** | Implicit | **Explicit** â |
| **Code Complexity** | Low | **Low-Medium** |
| **Lines of Code** | ~40 | ~45 (+5) |
| **Maintainability** | Good | **Excellent** â |

**Verdict**: File-static approach provides better software engineering for minimal cost (5 extra lines).

## Design Rationale

### Why File-Static in task.c?

1. **State transitions happen in task.c**: All state updates occur in `task_host_output()`
2. **Logical ownership**: task.c owns the screen update callback, so it should own the state
3. **Encapsulation**: State is only needed in task.c for transitions
4. **Performance**: Direct access within file (no function call overhead)

### Why Setter Function?

1. **Controlled initialization**: Clear interface for setting initial state
2. **Encapsulation**: Hides implementation detail (file-static variable)
3. **Future-proof**: Could add validation or logging if needed
4. **Minimal cost**: Only 5 lines of code

### Why Not Move elf_init() to task.c?

1. **Logical grouping**: Validation logic (`validate_elf_applid`) is in glue.c
2. **Separation of concerns**: glue.c handles ELF setup, task.c handles state transitions
3. **Maintainability**: Keeps related functions together

## Next Steps

1. **Implement file-static approach** (this document)
2. **Test compilation** on desktop and z/OS
3. **Test with ELF system** to verify automatic login
4. **Proceed to Phase 3**: TLS/SSL Certificate Integration

## Related Documents

- [`File-Static-Options-Analysis.md`](File-Static-Options-Analysis.md) - Analysis of file-static options
- [`Global-vs-Parameter-State-Analysis.md`](Global-vs-Parameter-State-Analysis.md) - Global variable analysis
- [`Phase2-Code-Changes-Enum.md`](Phase2-Code-Changes-Enum.md) - Original enum-based design (global variable)
- [`task_host_output-call-chain.md`](task_host_output-call-chain.md) - Call chain analysis
- [`Phase1-Code-Changes.md`](Phase1-Code-Changes.md) - ELF App ID transmission (completed)