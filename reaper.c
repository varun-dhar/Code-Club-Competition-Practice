#include <sys/prctl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>

void set_deathsig(int sig){
	if(prctl(PR_SET_PDEATHSIG,sig) == -1){
		perror("prctl");
		exit(1);
	}
}
