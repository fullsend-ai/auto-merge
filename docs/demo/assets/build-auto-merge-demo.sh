#!/usr/bin/env bash
set -euo pipefail

asset_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
output_dir=$(cd "${asset_dir}/.." && pwd)
render_dir="${asset_dir}/.render"
mkdir -p "${render_dir}"

scenes=(
  "00-title.svg"
  "01-pr-open.png"
  "02-ci-running.png"
  "03-review-running.png"
  "04-review-finding.png"
  "05-review-fix-rerun.png"
  "04-flow.svg"
  "06-auto-merge-running.png"
  "07-pending-receipt.png"
  "08-merged.png"
)

for scene in "${scenes[@]}" narration.mp3 captions.srt; do
  if [[ ! -f "${asset_dir}/${scene}" ]]; then
    echo "missing demo asset: ${asset_dir}/${scene}" >&2
    exit 1
  fi
done

for index in "${!scenes[@]}"; do
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "${asset_dir}/${scenes[$index]}" -t 15 \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x07111f,zoompan=z='min(zoom+0.00008,1.03)':d=450:s=1920x1080:fps=30,fade=t=in:st=0:d=0.45,fade=t=out:st=14.55:d=0.45,setsar=1,format=yuv420p" \
    -an -c:v libopenh264 -b:v 5M \
    "${render_dir}/scene-${index}.mp4"
done

ffmpeg -hide_banner -loglevel error -y \
  -i "${render_dir}/scene-0.mp4" \
  -i "${render_dir}/scene-1.mp4" \
  -i "${render_dir}/scene-2.mp4" \
  -i "${render_dir}/scene-3.mp4" \
  -i "${render_dir}/scene-4.mp4" \
  -i "${render_dir}/scene-5.mp4" \
  -i "${render_dir}/scene-6.mp4" \
  -i "${render_dir}/scene-7.mp4" \
  -i "${render_dir}/scene-8.mp4" \
  -i "${render_dir}/scene-9.mp4" \
  -filter_complex "[0:v][1:v][2:v][3:v][4:v][5:v][6:v][7:v][8:v][9:v]concat=n=10:v=1:a=0[v]" \
  -map "[v]" -an -c:v libopenh264 -b:v 6M \
  "${render_dir}/silent.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "${render_dir}/silent.mp4" \
  -i "${asset_dir}/narration.mp3" \
  -i "${asset_dir}/captions.srt" \
  -filter_complex "[1:a]apad=whole_dur=150[a]" \
  -map 0:v:0 -map "[a]" -map 2:0 \
  -t 150 -c:v copy -c:a aac -b:a 192k -c:s mov_text \
  -metadata title="Fullsend Auto-Merge: private-lab proof" \
  -metadata:s:s:0 language=eng \
  "${output_dir}/auto-merge-lab-demo.mp4"

ffprobe -v error \
  -show_entries format=duration,size:stream=index,codec_name,codec_type \
  -of default=noprint_wrappers=1 \
  "${output_dir}/auto-merge-lab-demo.mp4"
