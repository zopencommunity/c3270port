#include <fcntl.h>
#include <stdio.h>
#include <zos.h>

int main()
{
  int fd = open("/dev/null", 0);
  if (!fd) {
    perror("unable to open /dev/null");
    return 4;
  } else {
    printf("Success.\n");
    return 0;
  }
}
