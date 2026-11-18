#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <signal.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <string.h>
static volatile sig_atomic_t stop=0;
static volatile uint64_t sink=0;
static void quit(int s){(void)s;stop=1;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
int main(int argc,char **argv){
 if(argc!=3)return 2;
 signal(SIGTERM,quit);signal(SIGINT,quit);
 size_t n=64*1024*1024/sizeof(uint64_t);volatile uint64_t *a=NULL;
 if(!strcmp(argv[1],"memory")){a=malloc(n*sizeof(uint64_t));if(!a)return 3;for(size_t i=0;i<n;i++)a[i]=i*17+13;}
 FILE*f=fopen(argv[2],"wx");if(!f)return 4;fprintf(f,"%ld\n",(long)getpid());fclose(f);
 double start=now();uint64_t rounds=0,x=0x9e3779b97f4a7c15ULL;
 while(!stop && now()-start<35){
  if(!strcmp(argv[1],"cpu")){for(int k=0;k<1000000;k++){x^=x<<13;x^=x>>7;x^=x<<17;}sink=x;}
  else if(a){for(size_t i=0;i<n;i++)a[i]=a[i]*13+rounds;sink=a[rounds%n];}
  else {struct timespec t={0,50000000};nanosleep(&t,NULL);}
  rounds++;
 }
 printf("{\"mode\":\"%s\",\"rounds\":%llu,\"elapsed_s\":%.6f,\"sink\":%llu}\n",argv[1],(unsigned long long)rounds,now()-start,(unsigned long long)sink);
 free((void*)a);return 0;
}
