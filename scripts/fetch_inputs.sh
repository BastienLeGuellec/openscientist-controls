#!/usr/bin/env bash
# Download the authors' deposited inputs from Zenodo (record 23988648, concept DOI 10.5281/zenodo.18852838),
# check their md5 against the record, and unpack them where the other scripts expect them:
#   zenodo/cs3_main/job_a66ae54c/                        case study 3 main run, with the input h5ad
#   zenodo/cs3_online30/bourdenx-benchmark-2026-08-14/   the 30 online benchmark runs and PROMPT.txt
#   zenodo/other_cs/cs4/job_61204d0a/, job_586ae72a/     case study 4, phases 1 and 2
# Usage: scripts/fetch_inputs.sh   (needs curl, python3, tar; about 600 MB)
set -euo pipefail
cd "$(dirname "$0")/.."
REC=23988648
mkdir -p zenodo/cs3_main zenodo/cs3_online30 zenodo/other_cs/cs4
curl -sfL "https://zenodo.org/api/records/$REC" -o zenodo/record.json
get() {  # file key, destination directory
  local line url sum
  line=$(python3 -I -c "
import json,sys
for f in json.load(open('zenodo/record.json'))['files']:
    if f['key']==sys.argv[1]: print(f['links']['self'], f['checksum'].split(':')[1])" "$1")
  url=${line% *}; sum=${line#* }
  [ -f "zenodo/$1" ] || curl -sfL "$url" -o "zenodo/$1"
  echo "$sum  zenodo/$1" | md5sum -c --quiet
  tar xzf "zenodo/$1" -C "$2" --exclude='._*'
  echo "unpacked $1 into $2"
}
get Case_study_3_NFT_Transcriptomics_job_a66ae54c_data.tar.gz zenodo/cs3_main
get Case_study_3_NFT_Transcriptomics_supplemental_online_30runs_data.tar.gz zenodo/cs3_online30
get Case_study_4_Multiple_Myeloma_job_61204d0a_data.tar.gz zenodo/other_cs/cs4
get Case_study_4_Multiple_Myeloma_job_586ae72a_data.tar.gz zenodo/other_cs/cs4
