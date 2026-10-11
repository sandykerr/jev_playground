#!/usr/bin/env bash
#SBATCH --job-name=jev-routing-eval
#SBATCH --cpus-per-task=4
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=jev-routing-%j.out
set -euo pipefail

: "${SLURM_JOB_ID:?Submit this script with sbatch; do not benchmark locally}"
: "${LECOSPY_REPO_ROOT:?Set the absolute HPC checkout path}"
: "${LECOSPY_CONTAINER:?Set the project container image path}"
runtime="${LECOSPY_CONTAINER_RUNTIME:-apptainer}"
workers="${JEV_WORKERS:-${SLURM_CPUS_PER_TASK:-1}}"
cd "$LECOSPY_REPO_ROOT"
git rev-parse HEAD
git status --short
"$runtime" exec --cleanenv --bind "$LECOSPY_REPO_ROOT:$LECOSPY_REPO_ROOT" \
    --pwd "$LECOSPY_REPO_ROOT" \
    --env "SLURM_JOB_ID=$SLURM_JOB_ID,SLURM_CPUS_PER_TASK=${SLURM_CPUS_PER_TASK:-1},OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,MKL_NUM_THREADS=1" \
    "$LECOSPY_CONTAINER" python3 jev_routing/scripts/benchmark_routing.py --workers "$workers"
