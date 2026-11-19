#!/usr/bin/env python3
import argparse,subprocess
from pathlib import Path
EXPECTED='c656510ab81d31d413dc4dfd74b42671532cd978'
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('path'); a=ap.parse_args(); p=Path(a.path); head=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip(); assert head==EXPECTED,(head,EXPECTED)
 required=['capture-guide/consignes_T1.json','config/T1_special_menu_template_v1_0_0.json','schemas','tools','.github/workflows']
 for x in required: assert (p/x).exists(),x
 print('T1_BASELINE_READ_ONLY_OK',head)
if __name__=='__main__': main()
