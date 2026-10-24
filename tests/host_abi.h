/* Load host CRT declarations before the port's 32-bit pointer typedefs.
   These tests exercise portable formats/cryptography, not Toolbox pointers. */
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#undef SIZE_MAX
#define intptr_t gh_native_intptr_t
#define uintptr_t gh_native_uintptr_t
