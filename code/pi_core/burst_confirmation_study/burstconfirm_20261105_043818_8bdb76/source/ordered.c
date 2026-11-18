#define _GNU_SOURCE
#include <stdint.h>
#include <stdlib.h>
#include <sched.h>
#include <time.h>
static double mono(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+1e-9*t.tv_nsec;}
void *prepare(size_t n){volatile uint64_t *p=malloc(n);if(!p)return NULL;for(size_t i=0;i<n/8;i++)p[i]=i*17+13;return (void*)p;}
uint64_t phase(void *ptr,size_t n,int memory,uint64_t *ops,double *elapsed){cpu_set_t set;CPU_ZERO(&set);CPU_SET(3,&set);if(sched_setaffinity(0,sizeof(set),&set))return UINT64_MAX;volatile uint64_t *p=ptr;size_t len=n/8,pos=0;uint64_t k=0,x=0x9e3779b97f4a7c15ULL;double t=mono();while(mono()-t<1.0){if(memory){for(int j=0;j<4096;j++){p[pos]=p[pos]*13+k;pos++;if(pos==len)pos=0;k++;}}else{for(int j=0;j<4096;j++){x^=x<<13;x^=x>>7;x^=x<<17;k++;}}}*ops=k;*elapsed=mono()-t;return memory?p[pos?pos-1:0]:x;}
void release(void *p){free(p);}
