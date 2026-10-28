## Description of patches

`zos-cookie-io.patch` is a candidate fix for cookie file encoding on z/OS.
It applies to suite3270 4.4ga6, the version selected in `buildenv`.

Cookie file descriptors explicitly disable automatic conversion before I/O using
zoslib's `__disableautocvt()`. Files created or truncated to generate a cookie are
tagged binary (CCSID 65535) using zoslib's `__setfdbinary()`.
The emulator and x3270if use the same open helper, and conversion/tagging failures
follow the existing open-error paths. Existing nonempty files are not retagged.

The patch also adds an integration test using the actual x3270if client across
creation, empty-file generation, existing cookies with trailing whitespace, and
emulator restart.

This establishes raw cookie bytes for the ASCII zopen build. It does not convert
existing EBCDIC cookie contents or repair cookies corrupted by earlier writes.
Such files must be converted correctly or regenerated; changing a tag alone
does not convert contents.

Validation:

- Built s3270 and x3270if on macOS; all seven cookie tests passed.
- Compiled the actual open helper with IBM Clang on z/OS, linked it against the
  installed zoslib library, and tested with
  `_BPXK_AUTOCVT=ON`: new files, empty EBCDIC-tagged files, and reads of ASCII
  bytes in files tagged 0, 819, 1047, 1208, and 65535 passed. Generated files
  were checked for binary tags and disabled descriptor conversion.
- Full `zopen build` and s3270/x3270if authentication on z/OS are still pending.
  Peter's exact failure has not been reproduced.
