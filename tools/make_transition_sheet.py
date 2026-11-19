#!/usr/bin/env python3
import argparse, math
from pathlib import Path
import cv2
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('video'); a=ap.parse_args(); p=ROOT/a.video; times=[0,.2,.4,3,5.8,6,6.2,9.8,10,10.2,13.8,14,14.2,17.3,17.5,17.7,20.8,21,21.2,25,29.5]; cap=cv2.VideoCapture(str(p)); cards=[]
 for t in times:
  cap.set(cv2.CAP_PROP_POS_MSEC,t*1000); ok,f=cap.read(); assert ok; f=cv2.cvtColor(f,cv2.COLOR_BGR2RGB); im=Image.fromarray(f).resize((180,320)); c=Image.new('RGB',(180,344),'white'); c.paste(im,(0,24)); ImageDraw.Draw(c).text((5,5),f'{t:05.2f}s',fill='black'); cards.append(c)
 cap.release(); cols=7; rows=math.ceil(len(cards)/cols); board=Image.new('RGB',(cols*180,rows*344),(230,230,230))
 for i,c in enumerate(cards): board.paste(c,((i%cols)*180,(i//cols)*344))
 out=ROOT/'proofs/T2_SILENT_TRANSITIONS_CONTACT_SHEET.jpg'; out.parent.mkdir(exist_ok=True); board.save(out,quality=92); print(out)
if __name__=='__main__': main()
