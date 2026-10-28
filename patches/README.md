## Description of patches

`x3270if.c.patch` adds the termios header required by the z/OS build.

`zos-cookie-io.patch` makes cookie I/O consistent on z/OS. It applies after
`x3270if.c.patch` on suite3270 4.4ga6.

Generated cookies contain ASCII protocol bytes and are tagged binary with
zoslib's `__setfdbinary()`. Cookie descriptors first disable inherited conversion
with `__disableautocvt()`. Existing tagged text files in other encodings,
including IBM-1047, explicitly enable descriptor conversion to ASCII using
`F_CONTROL_CVT`. Reads preserve existing bytes and tags. Untagged, binary,
819, and 1208 files are read without translation. The emulator and x3270if use
the same helper, and descriptor errors follow the existing open-error paths.

Files whose tags do not match their contents must be repaired; encoding is not
guessed. The descriptor conversion mechanism must support the tagged CCSID.

The build runs [script-port and encoding checks](../testing/check-cookie-encoding.py)
against both a plain ASCII socket client and x3270if. See
[validation and client usage](../testing/COOKIE-REVIEW.md) for details.
