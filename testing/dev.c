#include <fcntl.h>
#include <stdio.h>
#include <zos.h>

/*
 * Assertion failed: dev_null >= 0, file: ../../../../Common/Test/json_test.c, line: 124, function: main
 * CEE5207E The signal SIGABRT was received.
 */
int main()
{
  int fd = open("/dev/null", 0);
  if (fd < 0) {
    perror("unable to open /dev/null");
    return 4;
  } else {
    printf("Success. fd:%d\n", fd);
    return 0;
  }
}
