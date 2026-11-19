import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class T2ContractTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cfg=json.loads((ROOT/'config/T2_avant_apres_template_v0_1_0.json').read_text()); cls.guide=json.loads((ROOT/'capture-guide/consignes_T2.json').read_text()); cls.q=json.loads((ROOT/'form/questions_T2.json').read_text()); cls.job=json.loads((ROOT/'demo/input_demo.json').read_text())
 def test_four_scenes(self): self.assertEqual([x['seconds'] for x in self.cfg['scenes']],[6,8,7,9]); self.assertEqual(sum(x['seconds'] for x in self.cfg['scenes']),30)
 def test_twelve_screens(self): self.assertEqual(self.cfg['stable_screen_count'],12); self.assertEqual(len(self.cfg['scenes'])*len(self.cfg['capture_states']),12)
 def test_transitions(self):
  e=self.cfg['transition_budget']['events']; self.assertEqual(len(e),6)
  for r in (1,2,3): self.assertEqual([x['reference'] for x in e].count(r),2)
 def test_questions_map_to_json(self):
  self.assertEqual([x['id'] for x in self.q['fields']],['nom','produit','prix','whatsapp','quartier','accroche']); self.assertEqual([x['required'] for x in self.q['fields']],[True,True,True,True,True,False])
 def test_current_stage_silent_no_text(self): self.assertFalse(self.job['render_audio']); self.assertFalse(self.job['render_business_text']); self.assertEqual(self.job['render_stage'],'silent_transition_validation')
 def test_language(self): self.assertIn('fon, yoruba, français, anglais',self.guide['mention_langues_commune']); self.assertFalse(self.guide['audio']['parole_obligatoire']); self.assertTrue(self.guide['audio']['conserver_voix_capturee']); self.assertFalse(self.guide['audio']['sous_titres_automatiques'])
 def test_ui_manifest(self):
  ui=json.loads((ROOT/'ui-screens/manifest.json').read_text()); self.assertEqual(ui['stable_screen_count'],12); self.assertEqual(len(ui['screens']),12)
if __name__=='__main__': unittest.main()
