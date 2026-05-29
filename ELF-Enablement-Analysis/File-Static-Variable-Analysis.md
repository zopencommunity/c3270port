# File-Static Variable Analysis for ELF State

## Question

Can we use a file-static variable (declared with `static` in glue.c) instead of a global variable for `elf_state`?

## Access Pattern Analysis

### Where is `elf_state` Accessed?

Looking at the implementation plan:

1. **glue.c** - State is **written** (initialized and modified):
   - `elf_init()` - Sets initial state (DISABLED or SEND_USERID)
   - `send_elf_token()` - Does NOT modify state (only sends tokens)

2. **task.c** - State is **read and written**:
   - `task_host_output()` - Reads state and transitions through states
   - Updates: SEND_USERID â SEND_PASSWORD â COMPLETE â DISABLED

### Critical Finding

**The state is modified in TWO different files**:
- â `glue.c` - Initializes state in `elf_init()`
- â `task.c` - Transitions state in `task_host_output()`

## Can We Use File-Static?

### Answer: **NO** - We Cannot Use File-Static

**Reason**: The state must be accessible from **both** `glue.c` and `task.c`.

If we make it `static` in `glue.c`:
```c
// glue.c
static elf_state_t elf_state = ELF_DISABLED;  // â File-static

// task.c
void task_host_output(void) {
    if (elf_state != ELF_DISABLED) {  // â ERROR: Cannot access
        // ...
    }
}
```

**Result**: Compilation error - `task.c` cannot access `elf_state`.

## Alternative: Accessor Functions

We could use accessor functions to hide the static variable:

```c
// glue.h
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

elf_state_t elf_get_state(void);
void elf_set_state(elf_state_t new_state);
void send_elf_token(const char *token);

// glue.c
static elf_state_t elf_state = ELF_DISABLED;  // â File-static

elf_state_t elf_get_state(void) {
    return elf_state;
}

void elf_set_state(elf_state_t new_state) {
    elf_state = new_state;
}

// task.c
void task_host_output(void) {
    if (elf_get_state() != ELF_DISABLED && IN_3270 && CAN_PROCEED) {
        switch (elf_get_state()) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");
                elf_set_state(ELF_SEND_PASSWORD);
                break;
            case ELF_SEND_PASSWORD:
                send_elf_token(")PSS.WD(");
                elf_set_state(ELF_COMPLETE);
                break;
            case ELF_COMPLETE:
                elf_set_state(ELF_DISABLED);
                break;
        }
    }
}
```

### Accessor Functions: Pros and Cons

**Advantages**:
â Encapsulation - State is hidden behind functions
â File-static variable - Not globally visible
â Could add validation in setters
â Could add logging/tracing in accessors

**Disadvantages**:
â More verbose - `elf_get_state()` vs `elf_state`
â Function call overhead (minimal, but exists)
â More complex - 2 extra functions to maintain
â Overkill for simple state variable
â Not consistent with c3270 patterns (c3270 uses direct access)

## Comparison: Global vs File-Static with Accessors

| Aspect | Global Variable | File-Static + Accessors |
|--------|----------------|-------------------------|
| **Encapsulation** | Low | High |
| **Code Simplicity** | High | Medium |
| **Performance** | Direct access | Function call overhead |
| **Verbosity** | Low | High |
| **Consistency** | Matches c3270 | Inconsistent with c3270 |
| **Maintenance** | Easy | More complex |
| **Lines of Code** | ~40 lines | ~60 lines |

## Recommendation

### Use Global Variable (Not File-Static)

**Rationale**:

1. **Cross-file access required**: State must be accessible from both `glue.c` and `task.c`

2. **Accessor functions are overkill**: 
   - No validation needed (enum is type-safe)
   - No side effects needed
   - Just adds complexity without benefit

3. **Consistency with c3270**:
   - c3270 uses direct global access for similar state
   - Example: `cursor_addr`, `buffer_addr`, `formatted` in ctlr.c

4. **Simplicity**:
   - Direct access: `if (elf_state == ELF_SEND_USERID)`
   - vs Accessor: `if (elf_get_state() == ELF_SEND_USERID)`

5. **Performance**:
   - Direct access is faster (no function call overhead)
   - Called on every screen update (performance matters)

## Implementation

### Recommended Approach

```c
// glue.h
typedef enum {
    ELF_DISABLED = 0,
    ELF_SEND_USERID,
    ELF_SEND_PASSWORD,
    ELF_COMPLETE
} elf_state_t;

/**
 * ELF authentication state.
 * 
 * Tracks the progress of ELF automatic authentication.
 * Modified by:
 * - elf_init() in glue.c (initialization)
 * - task_host_output() in task.c (state transitions)
 * 
 * This is a per-connection singleton state.
 */
extern elf_state_t elf_state;

void send_elf_token(const char *token);

// glue.c
elf_state_t elf_state = ELF_DISABLED;

void elf_init(void) {
    // Initialize state
    elf_state = (valid_elf_applid) ? ELF_SEND_USERID : ELF_DISABLED;
}

// task.c
#include "glue.h"

void task_host_output(void) {
    // Direct access to elf_state
    if (elf_state != ELF_DISABLED && IN_3270 && CAN_PROCEED) {
        switch (elf_state) {
            case ELF_SEND_USERID:
                send_elf_token(")USR.ID(");
                elf_state = ELF_SEND_PASSWORD;
                break;
            // ... etc
        }
    }
}
```

## Why Not File-Static?

**Summary**:
- â Cannot use file-static because state is accessed from multiple files
- â Accessor functions add complexity without benefit
- â Global variable with clear documentation is the right choice
- â Matches c3270 architecture and patterns

## Conclusion

**Use a global variable (with `extern` declaration in header).**

File-static would require accessor functions, which add unnecessary complexity for a simple state variable that needs cross-file access. The global variable approach is:
- Simpler
- Faster
- More consistent with c3270
- Easier to maintain

The key is **good documentation** (which we have) rather than artificial encapsulation that doesn't provide real benefit.