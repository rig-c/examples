import importlib.util
from pathlib import Path
import unittest
import io
from PIL import Image
spec=importlib.util.spec_from_file_location('preview_loop',Path(__file__).with_name('preview-loop.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LoopControls(unittest.TestCase):
 def test_fixed_normal_defect_edges(self):
  self.assertTrue(m.controls()['PASS'])
 def test_alpha_one_visible_defect_is_not_rounded_away(self):
  a=Image.new('RGBA',(2,2),(0,0,0,1));b=a.copy();b.putpixel((0,0),(1,0,0,1));self.assertEqual(m.visible_difference(a,b),1)
 def test_pillow_animated_encoder_reader_timing_alpha_roundtrip(self):
  a=Image.new('RGBA',(8,8),(0,0,0,0));a.putpixel((3,3),(255,0,0,255));a.putpixel((4,3),(128,64,32,128));b=a.copy();b.putpixel((3,3),(0,255,0,255));out=io.BytesIO();a.save(out,format='WEBP',save_all=True,append_images=[b],duration=[1667,1666],loop=0,lossless=False,quality=75,alpha_quality=100,method=4,minimize_size=True);out.seek(0)
  images=[];times=[]
  with Image.open(out)as im:
   self.assertEqual(im.n_frames,2);self.assertEqual(im.info['loop'],0)
   for i in range(im.n_frames):im.seek(i);im.load();images.append(im.convert('RGBA'));times.append(im.info['duration'])
  self.assertTrue(m.check_loop(images,times,0,(a,a))['PASS']);self.assertEqual(images[0].getchannel('A').tobytes(),a.getchannel('A').tobytes())
if __name__=='__main__':unittest.main()
