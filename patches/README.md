## Description of patches

- **./c3270/Makefile.obj.in.patch** : `mkkeypad` needs an explicit rule because the default rule does not pull in libraries such as `zoslib` which is required to bind. 
- **./lib/3270/Makefile.obj.in.patch** : `mkicon` needs an explicit rule because the default rule does not pull in libraries such as `zoslib` which is required to bind.
- **./s3270/Makefile.obj.in.patch** : `mkfb` does not pull in libraries such as `zoslib`, so the libraries need to be added to the bind.
- **./c3270/configure.patch** : remove `curses` from the list of _curses_ libraries to search because we want to ensure we get our `ncurses` and not the z/OS `curses`
