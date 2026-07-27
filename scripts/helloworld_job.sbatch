#!/bin/bash
#SBATCH --job-name=helloworld
#SBATCH --partition=debug
#SBATCH --time=00:05:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=results/helloworld/%j.out

python3 -c "import socket, sys; print(f'hello world from {socket.gethostname()} (python {sys.version.split()[0]})')"
