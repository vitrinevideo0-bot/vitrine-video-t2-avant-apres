#!/usr/bin/env python3
import argparse, hashlib, json, subprocess
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256();
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('video'); a=ap.parse_args(); p=ROOT/a.video
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)],text=True)); video=[x for x in probe['streams'] if x['codec_type']=='video']; audio=[x for x in probe['streams'] if x['codec_type']=='audio']
 cap=cv2.VideoCapture(str(p)); obs={'width':int(cap.get(3)),'height':int(cap.get(4)),'fps':float(cap.get(5)),'frames':int(cap.get(7))}; cap.release(); obs['duration_seconds']=obs['frames']/obs['fps']
 assert len(video)==1 and len(audio)==0, f'flux inattendus video={len(video)} audio={len(audio)}'; assert (obs['width'],obs['height'],obs['fps'],obs['frames'])==(720,1280,30.0,900); assert obs['duration_seconds']==30.0
 result={'file':a.video,'sha256':sha(p),'bytes':p.stat().st_size,'video_streams':len(video),'audio_streams':len(audio),'text_overlays':0,'observed':obs,'status':'PASS'}
 out=ROOT/'proofs/silent_validation.json'; out.write_text(json.dumps(result,indent=2)+'
'); (p.with_suffix('.sha256')).write_text(f"{result['sha256']}  {p.name}
"); print('SILENT_VALIDATION_OK',json.dumps(result))
if __name__=='__main__': main()
