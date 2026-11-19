#!/usr/bin/env python3
"""Rendu serveur T2 silencieux : rushes + six transitions, aucun texte."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import cv2, numpy as np
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from engine.media import ClipSpec, SequentialClip, cover_9x16, warm_grade
from engine.transitions import intro_oblique, center_window_expand, warm_flash, oblique_shutters, staggered_bands, diagonal_desaturated_to_color

def digest(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

def render(job_path):
 job=json.loads(Path(job_path).read_text()); cfg=json.loads((ROOT/'config/T2_avant_apres_template_v0_1_0.json').read_text()); man=json.loads((ROOT/job['rush_manifest']).read_text())
 if job.get('render_audio') is not False or job.get('render_business_text') is not False: raise ValueError('Cette étape doit rester muette et sans texte')
 W,H,FPS,N=720,1280,30,900; out=ROOT/job['output']; out.parent.mkdir(parents=True,exist_ok=True); tmp=out.with_suffix('.server-silent.mp4')
 clips=[]
 for src in sorted(man['sources'],key=lambda x:x['scene']):
  p=ROOT/src['local_file']; actual=digest(p)
  if actual!=src['sha256']: raise ValueError(f'SHA invalide {p.name}: {actual}')
  clips.append(SequentialClip(ClipSpec(p,float(src['edit']['start']),float(src['edit']['duration']))))
 writer=cv2.VideoWriter(str(tmp),cv2.VideoWriter_fourcc(*'mp4v'),FPS,(W,H))
 if not writer.isOpened(): raise RuntimeError('VideoWriter indisponible')
 durations=[6.,8.,7.,9.]; starts=[0.,6.,14.,21.]
 def frame(i,local):
  p=float(np.clip(local/durations[i],0,1)); z=[(1.015,1.070),(1.035,1.055),(1.020,1.055),(1.018,1.050)][i]; px=[-.12+.22*p,.08-.12*p,-.06+.12*p,0][i]; py=[.02,-.08+.14*p,.01,-.03+.07*p][i]
  return warm_grade(cover_9x16(clips[i].frame(local),W,H,z[0]+(z[1]-z[0])*p,px,py))
 try:
  for n in range(N):
   t=n/FPS; i=0 if t<6 else 1 if t<14 else 2 if t<21 else 3; img=frame(i,t-starts[i])
   if t<.42: img=intro_oblique(img,t/.42)
   if 5.79<=t<6.21: img=center_window_expand(frame(0,min(5.999,t)),frame(1,max(0,t-6)),(t-5.79)/.42)
   if 9.79<=t<10.21: img=warm_flash(img,(t-9.79)/.42)
   if 13.79<=t<14.21: img=oblique_shutters(frame(1,min(7.999,max(0,t-6))),frame(2,max(0,t-14)),(t-13.79)/.42)
   if 17.29<=t<17.71: img=staggered_bands(img,(t-17.29)/.42)
   if 20.79<=t<21.21: img=diagonal_desaturated_to_color(frame(2,min(6.999,max(0,t-14))),frame(3,max(0,t-21)),(t-20.79)/.42)
   writer.write(img)
   if n%90==0: print(f'frame {n}/{N}',flush=True)
 finally:
  writer.release()
  for c in clips: c.close()
 import imageio_ffmpeg
 ff=imageio_ffmpeg.get_ffmpeg_exe(); cmd=[ff,'-y','-i',str(tmp),'-an','-t','30.000','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','30','-movflags','+faststart','-metadata','title=T2 transitions silencieuses serveur',str(out)]
 r=subprocess.run(cmd,text=True,capture_output=True)
 if r.returncode: raise RuntimeError(r.stderr[-4000:])
 tmp.unlink(missing_ok=True)
 proof={'output':str(out.relative_to(ROOT)),'sha256':digest(out),'bytes':out.stat().st_size,'width':W,'height':H,'fps':FPS,'frames':N,'duration_seconds':30.0,'audio_streams':0,'text_overlays':0,'generated_by':'GitHub Actions','transitions':cfg['transition_budget']['events']}
 (ROOT/'proofs').mkdir(exist_ok=True); (ROOT/'proofs/server_render_manifest.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'
')
 print('SERVER_SILENT_RENDER_OK',out)
 return out

if __name__=='__main__':
 ap=argparse.ArgumentParser(); ap.add_argument('--job',default='demo/input_demo.json'); a=ap.parse_args(); render(ROOT/a.job if not Path(a.job).is_absolute() else Path(a.job))
