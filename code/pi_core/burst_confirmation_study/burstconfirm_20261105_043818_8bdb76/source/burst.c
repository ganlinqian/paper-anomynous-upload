#define _GNU_SOURCE
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <sched.h>
static double mono(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+1e-9*t.tv_nsec;}
void *prepare(size_t n){volatile uint64_t *p=malloc(n);if(!p)return NULL;for(size_t i=0;i<n/8;i++)p[i]=i*17+13;return (void*)p;}
uint64_t burst(void *ptr,size_t n,unsigned ms,uint64_t *ops,double *elapsed){
 cpu_set_t set;CPU_ZERO(&set);CPU_SET(3,&set);if(sched_setaffinity(0,sizeof(set),&set))return UINT64_MAX;
 volatile uint64_t *p=ptr;size_t count=n/8,pos=0;uint64_t k=0;double t=mono();
 while(ms && (mono()-t)*1000.0<ms){for(int j=0;j<4096;j++){p[pos]=p[pos]*13+k;pos++;if(pos==count)pos=0;k++;}}
 *elapsed=mono()-t;*ops=k;return p[pos?pos-1:0];
}
void release(void *p){free(p);}
