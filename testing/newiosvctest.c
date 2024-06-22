
#include <stdio.h>
#include <sys/stat.h>
#include <sys/time.h>

#ifdef __MVS__
#include <fcntl.h>
#include <zos.h>
#endif

#ifdef __MVS__
FILE* __tmpfiletxt(void)
{
	FILE* f;
	char* n;
	f = tmpfile();

	if (f == NULL) {
		return NULL;
	} else {
		/*
		 * Underlying descriptor needs to be W+ and not WB+
		 */
		int fno = fileno(f);

		int rc = fcntl(fno, F_SETFD, O_RDWR|O_CREAT|O_APPEND);
		if (rc) {
			return NULL;
		}
	}
	int fd = fileno(f);
	if (__chgfdccsid(fd, 819)) {
		return NULL;
	}
	return f;
}
#endif

static FILE *
mkfb_tmpfile(void)
{
    FILE *f;
#if defined(_WIN32) /*[*/
    char *n;
#endif /*]*/

#if !defined(_WIN32) && !defined(__MVS__) /*[*/
    f = tmpfile();
    if (f == NULL) {
        perror("tmpfile");
        exit(1);
    }
#else /*][*/
	#if defined(_WIN32)
	    n = _tempnam(NULL, "mkfb");
	    if (n == NULL) {
		fprintf(stderr, "_tempnam failed.\n");
		exit(1);
	    }
	    f = fopen(n, "w+b");
	    if (f == NULL) {
		fprintf(stderr, "_tempnam open(\"%s\") failed: %s\n", n,
			strerror(errno));
		exit(1);
	    }
	    free(n);
	#else
	    f = __tmpfiletxt();
	    if (f == NULL) {
		perror("tmpfile");
		exit(1);
	    }
	#endif
#endif /*]*/

    return f;
}

int cmain(int argc, char* argv[])
{

#ifdef __MVS__
	zoslib_config_t c;
	init_zoslib(c);
#endif

	FILE* f = mkfb_tmpfile();
	char buf[80];
	if (f) {
		fprintf(f, "%s\n", "Hello world");
		rewind(f);
		fgets(buf, sizeof(buf), f);
		fprintf(stderr, "%s", buf);
		fclose(f);
	} else {
		fprintf(stderr, "Unable to open file\n");
	}
	return 0;
}

