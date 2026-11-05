// LD_PRELOAD shim: keep every thread inside the process's starting CPU mask.
// onnxruntime (and possibly other runtimes) pin their worker threads to cores of
// their choosing, escaping `taskset`. This clamps any requested mask to the mask
// the process started with (set by `taskset -c 12-19`).
#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <sched.h>
#include <string.h>

static cpu_set_t base;
static int have_base = 0;

static int (*real_sched)(pid_t, size_t, const cpu_set_t *);
static int (*real_pthread)(pthread_t, size_t, const cpu_set_t *);
static int (*real_attr)(pthread_attr_t *, size_t, const cpu_set_t *);

__attribute__((constructor)) static void init(void) {
  real_sched = dlsym(RTLD_NEXT, "sched_setaffinity");
  real_pthread = dlsym(RTLD_NEXT, "pthread_setaffinity_np");
  real_attr = dlsym(RTLD_NEXT, "pthread_attr_setaffinity_np");
  CPU_ZERO(&base);
  if (sched_getaffinity(0, sizeof(base), &base) == 0) have_base = 1;
}

static void clamp(size_t size, const cpu_set_t *in, cpu_set_t *out) {
  CPU_ZERO(out);
  if (!have_base) { memcpy(out, in, size < sizeof(*out) ? size : sizeof(*out)); return; }
  CPU_AND(out, (cpu_set_t *)in, &base);
  if (CPU_COUNT(out) == 0) *out = base;
}

int sched_setaffinity(pid_t pid, size_t size, const cpu_set_t *mask) {
  cpu_set_t m; clamp(size, mask, &m);
  return real_sched(pid, sizeof(m), &m);
}
int pthread_setaffinity_np(pthread_t t, size_t size, const cpu_set_t *mask) {
  cpu_set_t m; clamp(size, mask, &m);
  return real_pthread(t, sizeof(m), &m);
}
int pthread_attr_setaffinity_np(pthread_attr_t *a, size_t size, const cpu_set_t *mask) {
  cpu_set_t m; clamp(size, mask, &m);
  return real_attr(a, sizeof(m), &m);
}
