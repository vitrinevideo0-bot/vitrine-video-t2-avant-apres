#!/usr/bin/env python3
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--answers',required=True); ap.add_argument('--output',required=True); a=ap.parse_args(); q=json.loads((ROOT/'form/questions_T2.json').read_text()); ans=json.loads((ROOT/a.answers).read_text()); ids={x['id'] for x in q['fields']}; assert set(ans)<=ids
 for f in q['fields']:
  v=ans.get(f['id'],''); assert (not f['required']) or str(v).strip(); assert len(str(v))<=f['maxLength']; assert len(str(v))>=f.get('minLength',0); assert not f.get('pattern') or re.fullmatch(f['pattern'],str(v))
 job={'template_id':'restaurants_maquis_T2_avant_apres_v0_1_0','business':ans,'rush_manifest':'rushes/manifest.json','output':'output/T2_AVANT_APRES_TRANSITIONS_SILENT_V0_2_0.mp4','render_stage':'silent_transition_validation','render_business_text':False,'render_audio':False}; (ROOT/a.output).write_text(json.dumps(job,ensure_ascii=False,indent=2)+'
'); print('RENDER_JOB_OK')
if __name__=='__main__': main()
