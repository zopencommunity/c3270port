## Description of patches

- cti.py.patch : this patch provides an alternate way to check if a port is being listened on that doesn't rely on netstat, which isn't portable.
- sa_malloc.c.patch : this patch provides a second definition of my_vasprintf, which is otherwise unresolved. This is not the right fix.
- 3270/Makefile.test.obj.in.patch and 32xx/Makefile.test.obj.in.patch : these patches add in the LDFLAGS and LIBS for the C tests that are built that need the zoslib routines.
- ./c3270/Test/test\*.py.patch : these patches temporarily skip tests that hang when run on z/OS due to (I think) a socket being left open.
