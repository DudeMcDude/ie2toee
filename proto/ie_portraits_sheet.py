import glob,sys
from PIL import Image,ImageDraw
A='/workspace/iemain-wt/art/portraits/';import ie_portraits
N=sys.argv[2:] or ['hrothgar','everard','arundel','poquelin','belhifet','yxunomei','kresselack','conlan']
W=310;sh=Image.new('RGB',(W*4,2*300),(30,30,30));d=ImageDraw.Draw(sh)
for i,n in enumerate(N):
  x=(i%4)*W+8;y=(i//4)*300+8;o=lambda k:Image.open(A+f'{n}/ie_{n}_{k}.png').convert('RGB')
  sh.paste(o('big'),(x,y));d.text((x,y+155),'%s %d'%(n,ie_portraits.ART_IDS[n][0]),fill='white')
  sh.paste(o('m'),(x+136,y));sh.paste(o('s'),(x+136,y+42))
  sh.paste(o('m').resize((126,111),Image.NEAREST),(x+180,y));sh.paste(o('s').resize((159,141),Image.NEAREST),(x,y+170)) if False else sh.paste(o('s').resize((126,112),Image.NEAREST),(x+180,y+115))
sh.save(sys.argv[1],quality=90)
